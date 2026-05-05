"""R8.5.0 — `GET /projects/{pid}/documents/{did}` must surface
`per_field_evidence` and `per_field_confidence` under `latest_prediction`
so the Studio popover can render quote/page/rationale evidence and the
confidence chip without a second roundtrip.

Spec §3.2 hard rule: evidence shape never carries bbox / coordinates /
polygon / region / span. The payload composition here must not introduce
any such key, even if backend models grow them by accident later.
"""

import io

import pytest

from app.models.prediction import Prediction


async def _auth_upload(client, tmp_path, monkeypatch) -> tuple[dict, int, int]:
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post(
        "/api/v1/auth/register", json={"email": "ev@ev.com", "password": "hunter22"}
    )
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "ev@ev.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (
        await client.post("/api/v1/projects", json={"name": "P"}, headers=h)
    ).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    return h, pid, did


@pytest.mark.asyncio
async def test_document_detail_surfaces_per_field_evidence_and_confidence(
    client, db_session, tmp_path, monkeypatch
):
    h, pid, did = await _auth_upload(client, tmp_path, monkeypatch)

    evidence = {
        "0": {
            "total": {
                "page": 1,
                "quote": "Total ¥1,234",
                "rationale": "Used the tax-included total line.",
            }
        }
    }
    confidence = {"0": {"total": "down"}}

    pred = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="x",
        output=[{"total": 1234}],
        per_field_confidence=confidence,
        per_field_evidence=evidence,
        status="success",
    )
    db_session.add(pred)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    latest = body["latest_prediction"]
    assert latest is not None
    assert latest["per_field_evidence"] == evidence
    assert latest["per_field_confidence"] == confidence


@pytest.mark.asyncio
async def test_document_detail_does_not_leak_forbidden_localization_keys(
    client, db_session, tmp_path, monkeypatch
):
    """Defense in depth: even if a Prediction somehow stores forbidden
    localization keys, the payload composition must not surface them.

    The engine already strips them on persist (see test_field_evidence.py),
    but the read path is a second checkpoint per CLAUDE.md red lines.
    """
    h, pid, did = await _auth_upload(client, tmp_path, monkeypatch)

    pred = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="x",
        output=[{"total": 1234}],
        per_field_confidence={"0": {"total": "up"}},
        per_field_evidence={
            "0": {
                "total": {
                    "page": 1,
                    "quote": "Total ¥1,234",
                    "rationale": "tax-included",
                }
            }
        },
        status="success",
    )
    db_session.add(pred)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    body = resp.json()

    serialized = repr(body)
    for forbidden in ("bbox", "coordinates", "polygon", "region", '"span"'):
        assert forbidden not in serialized, (
            f"Document detail payload must not surface '{forbidden}'"
        )


@pytest.mark.asyncio
async def test_document_detail_handles_null_evidence_and_confidence(
    client, db_session, tmp_path, monkeypatch
):
    """`per_field_evidence` is nullable on the model and `per_field_confidence`
    defaults to `{}`. The route must surface both keys regardless so the
    frontend doesn't need to defensively check for missing fields."""
    h, pid, did = await _auth_upload(client, tmp_path, monkeypatch)

    pred = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="x",
        output=[{"total": 1234}],
        status="success",
    )
    db_session.add(pred)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    body = resp.json()
    latest = body["latest_prediction"]
    assert latest is not None
    assert "per_field_evidence" in latest
    assert "per_field_confidence" in latest
    assert latest["per_field_evidence"] is None
    assert latest["per_field_confidence"] == {}
