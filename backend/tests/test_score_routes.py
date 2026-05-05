import io

import pytest
from sqlalchemy import select

from app.engine.judge import FakeJudgeProvider, get_judge_provider
from app.engine.recompute import DEFAULT_JUDGE_MODEL_VERSION
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document as D
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction, PredictionStatus
from app.models.project_version import ProjectVersion
from app.models.user import User


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "s@s.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "s@s.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_get_score_empty_project_is_one(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/score", headers=h)
    body = resp.json()
    assert body["score"] == 1.0  # no vibe-check, empty CE pool → trivially 1.0


@pytest.mark.asyncio
async def test_get_calibration_returns_prior_for_empty(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/calibration", headers=h)
    body = resp.json()
    assert body["point_estimate"] == pytest.approx(0.80, abs=1e-3)
    assert 0 <= body["ci_low"] <= body["ci_high"] <= 1


@pytest.mark.asyncio
async def test_review_queue_three_buckets(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    files = [("files", (f"{n}.pdf", io.BytesIO(b"X"), "application/pdf")) for n in "abc"]
    docs = (
        await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    ).json()

    for d, conf in zip(
        docs,
        [
            {"0": {"a": "up"}},  # full up → spot-check candidate
            {"0": {"a": "up", "b": "down"}},  # has down → required review
            {"0": {"a": "uncertain"}},  # has uncertain → required review
        ],
    ):
        db_session.add(
            Prediction(
                document_id=d["id"],
                model_id="m",
                prompt_hash="h",
                output=[{"a": 1}],
                per_field_confidence=conf,
                status=PredictionStatus.SUCCESS.value,
            )
        )
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/review-queue", headers=h)
    body = resp.json()
    assert len(body["required_review"]) == 2
    # spot_check is sampled (default 2 from the up-only set, but here we have 1)
    assert len(body["spot_check"]) <= 2
    assert {d["id"] for d in body["all"]} >= {d["id"] for d in body["required_review"]}


@pytest.mark.asyncio
async def test_get_score_with_unwired_rerun_treats_ce_pool_as_perfect(
    client, db_session, tmp_path, monkeypatch
):
    """When rerun is None (production wiring not yet in /score), a non-empty CE
    pool must NOT collapse the score to 0.7*judge — ce_component falls back to
    1.0 per spec §4.1 (empty-pool semantics).
    """
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"X"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]

    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()
    user = (await db_session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=pred.id,
            output=[{"a": 1}],
            role=AnnotationRole.COUNTEREXAMPLE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=user.id,
            last_modified_by=user.id,
        )
    )
    await db_session.commit()

    body = (await client.get(f"/api/v1/projects/{pid}/score", headers=h)).json()
    assert body["ce_component"] == 1.0
    assert body["score"] == 1.0  # judge_component also 1.0 (no vibe-check pairs)


@pytest.mark.asyncio
async def test_get_calibration_filters_by_default_judge_model(client, db_session):
    """A project with calibration rows for two different judge_model_versions must
    not blow up `/calibration`; the endpoint reads only the active/default model.
    """
    h, pid = await _auth_and_project(client)
    db_session.add(
        JudgeCalibration(
            project_id=pid,
            judge_model_version=DEFAULT_JUDGE_MODEL_VERSION,
            tp=3,
            fp=1,
        )
    )
    db_session.add(
        JudgeCalibration(
            project_id=pid, judge_model_version="some-old-judge", tp=99, fp=99
        )
    )
    await db_session.commit()

    body = (await client.get(f"/api/v1/projects/{pid}/calibration", headers=h)).json()
    assert body["tp"] == 3
    assert body["fp"] == 1


@pytest.mark.asyncio
async def test_trigger_judge_writes_per_field_confidence(
    client, db_session, tmp_path, monkeypatch, app
):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"X")
    files = [("files", ("a.pdf", io.BytesIO(b"X"), "application/pdf"))]
    did = (
        await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    ).json()[0]["id"]

    d = (await db_session.execute(select(D).where(D.id == did))).scalar_one()
    d.file_path = str(fp)
    version = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.project_id == pid)
        )
    ).scalar_one()
    pred = Prediction(
        document_id=did,
        project_version_id=version.id,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[{"0": {"a": "up"}}])
    app.dependency_overrides[get_judge_provider] = lambda: fake

    resp = await client.post(f"/api/v1/projects/{pid}/judge", headers=h)
    assert resp.status_code == 200
    await db_session.refresh(pred)
    assert pred.per_field_confidence == {"0": {"a": "up"}}


@pytest.mark.asyncio
async def test_review_queue_and_judge_pool_flip_with_lock_state(
    client, db_session, tmp_path, monkeypatch, app
):
    """Route-level pin for the gap-#51 fix: while the active schema is draft,
    /review-queue and /judge see the relaxed pool (corrected docs visible);
    once locked, both flip to spec §4.1 strict mode (corrected docs leave).

    Prevents a future caller-layer refactor from silently dropping the
    `include_corrected` kwarg pass-through. The unit test in test_recompute
    covers the helper; this test covers the wire-up.
    """
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)

    files = [
        ("files", ("a.pdf", io.BytesIO(b"A"), "application/pdf")),
        ("files", ("b.pdf", io.BytesIO(b"B"), "application/pdf")),
    ]
    docs = (
        await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    ).json()
    did_a, did_b = docs[0]["id"], docs[1]["id"]

    version = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.project_id == pid)
        )
    ).scalar_one()
    for did in (did_a, did_b):
        d = (await db_session.execute(select(D).where(D.id == did))).scalar_one()
        d.file_path = str(tmp_path / f"{did}.pdf")
        (tmp_path / f"{did}.pdf").write_bytes(b"X")
        db_session.add(
            Prediction(
                document_id=did,
                project_version_id=version.id,
                model_id="m",
                prompt_hash="h",
                output=[{"a": 1}],
                per_field_confidence={},
                status=PredictionStatus.SUCCESS.value,
            )
        )
    await db_session.commit()

    user = (await db_session.execute(select(User).order_by(User.id).limit(1))).scalar_one()
    db_session.add(
        Annotation(
            document_id=did_b,
            output=[{"a": 1}],
            role=AnnotationRole.NONE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=user.id,
            last_modified_by=user.id,
        )
    )
    await db_session.commit()

    # Draft schema → relaxed pool: both docs in /review-queue.all and both
    # picked up by /judge.
    body = (await client.get(f"/api/v1/projects/{pid}/review-queue", headers=h)).json()
    all_ids = {row["id"] for row in body["all"]}
    assert all_ids == {did_a, did_b}, (
        "draft mode must keep the corrected doc in review-queue.all"
    )

    fake = FakeJudgeProvider(canned=[{"0": {"a": "up"}}, {"0": {"a": "up"}}])
    app.dependency_overrides[get_judge_provider] = lambda: fake
    judged = (
        await client.post(f"/api/v1/projects/{pid}/judge", headers=h)
    ).json()
    assert len(judged["judged_predictions"]) == 2, (
        "draft mode must run judge on both predictions, including the "
        "corrected doc's prediction"
    )

    # Lock the active version → strict pool: corrected doc leaves both
    # surfaces.
    version.locked = True
    await db_session.commit()

    body = (await client.get(f"/api/v1/projects/{pid}/review-queue", headers=h)).json()
    all_ids = {row["id"] for row in body["all"]}
    assert all_ids == {did_a}, (
        "locked mode must drop the corrected doc per spec §4.1"
    )

    fake_locked = FakeJudgeProvider(canned=[{"0": {"a": "up"}}])
    app.dependency_overrides[get_judge_provider] = lambda: fake_locked
    judged = (
        await client.post(f"/api/v1/projects/{pid}/judge", headers=h)
    ).json()
    assert len(judged["judged_predictions"]) == 1, (
        "locked mode must run judge only on the uncorrected doc"
    )
