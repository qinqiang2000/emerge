import io

import pytest


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

    from app.models.prediction import Prediction, PredictionStatus

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
