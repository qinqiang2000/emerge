import pytest
from sqlalchemy import select


async def _auth_and_project(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


async def _patch_schema(client, headers, pid, schema):
    res = await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={"schema": schema, "global_notes": "", "model_id": "m"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_readiness_reports_no_production_feedback_not_100_percent(client, db_session):
    h, pid = await _auth_and_project(client, "rd1@rd.com")
    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["regression_health"]["counterexamples_total"] == 0
    assert body["regression_health"]["status"] == "no_production_feedback"
    assert "no_production_feedback" in body["warnings"]
    # CRITICAL: empty pool must NOT be presented as 100% certainty.
    assert body["regression_health"]["counterexample_component"] is None


@pytest.mark.asyncio
async def test_readiness_counts_human_review_coverage(client, db_session):
    from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
    from app.models.document import Document, DocumentStatus
    from app.models.prediction import Prediction, PredictionStatus

    h, pid = await _auth_and_project(client, "rd2@rd.com")
    # Add a doc, prediction, and saved annotation (role='none').
    doc = Document(
        project_id=pid,
        filename="r.pdf",
        file_path="/tmp/r.pdf",
        mime_type="application/pdf",
        page_count=1,
        byte_size=3,
        uploaded_by=1,
        status=DocumentStatus.EXTRACTED.value,
    )
    db_session.add(doc)
    await db_session.flush()
    pred = Prediction(
        document_id=doc.id,
        project_version_id=1,
        model_id="m",
        prompt_hash="h",
        output=[{"total": 1234}],
        per_field_confidence={},
        per_field_evidence={"0": {"total": {"page": 1, "quote": "X"}}},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.flush()
    ann = Annotation(
        document_id=doc.id,
        parent_prediction_id=pred.id,
        output=[{"total": 1234, "currency": "JPY"}],
        role=AnnotationRole.NONE.value,
        status=AnnotationStatus.SAVED.value,
        created_by=1,
        last_modified_by=1,
    )
    db_session.add(ann)
    await db_session.commit()

    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    assert res.status_code == 200, res.text
    coverage = res.json()["evidence_coverage"]
    assert coverage["reviewed_docs"] >= 1
    assert coverage["reviewed_entities"] >= 1
    assert coverage["reviewed_fields"] >= 2
    assert coverage["field_evidence_fields"] >= 1


@pytest.mark.asyncio
async def test_readiness_blocks_publish_without_active_version(client, db_session):
    from app.models.project import Project

    h, pid = await _auth_and_project(client, "rd3@rd.com")
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    proj.active_version_id = None
    await db_session.commit()

    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    assert res.status_code == 200, res.text
    assert "no_active_version" in res.json()["publish_blockers"]


@pytest.mark.asyncio
async def test_readiness_flags_unlocked_active_version(client, db_session):
    h, pid = await _auth_and_project(client, "rd4@rd.com")
    await _patch_schema(
        client,
        h,
        pid,
        [{"name": "total", "type": "number", "description": "total"}],
    )
    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    assert res.status_code == 200, res.text
    blockers = res.json()["publish_blockers"]
    assert "active_version_unlocked" in blockers


@pytest.mark.asyncio
async def test_readiness_flags_empty_schema(client, db_session):
    """Initial project has empty active version schema → empty_schema blocker."""
    h, pid = await _auth_and_project(client, "rd5@rd.com")
    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    assert res.status_code == 200, res.text
    assert "empty_schema" in res.json()["publish_blockers"]


@pytest.mark.asyncio
async def test_readiness_schema_maturity_default_is_draft(client, db_session):
    h, pid = await _auth_and_project(client, "rd6@rd.com")
    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    body = res.json()
    assert body["schema_maturity"]["status"] in ("draft", "stabilizing")


@pytest.mark.asyncio
async def test_readiness_returns_quality_estimate_with_ci(client, db_session):
    h, pid = await _auth_and_project(client, "rd7@rd.com")
    res = await client.get(f"/api/v1/projects/{pid}/readiness", headers=h)
    body = res.json()
    qe = body["quality_estimate"]
    assert 0.0 <= qe["judge_precision"] <= 1.0
    assert qe["ci_low"] <= qe["judge_precision"] <= qe["ci_high"]


@pytest.mark.asyncio
async def test_readiness_404_for_other_workspace_project(client, db_session):
    h_a, pid_a = await _auth_and_project(client, "rdA@rd.com")
    # second user should not see project A (different workspace via auto-create).
    await client.post(
        "/api/v1/auth/register", json={"email": "rdB@rd.com", "password": "hunter22"}
    )
    tok_b = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "rdB@rd.com", "password": "hunter22"},
        )
    ).json()["access_token"]
    h_b = {"Authorization": f"Bearer {tok_b}"}
    res = await client.get(f"/api/v1/projects/{pid_a}/readiness", headers=h_b)
    assert res.status_code == 404
