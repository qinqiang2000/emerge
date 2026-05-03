import pytest
from sqlalchemy import select

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.user import User


async def _auth_and_project(client, email="lk@lk.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_lock_status_initially_blocked(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/lock-status", headers=h)
    body = resp.json()
    assert body["can_lock"] is False
    assert "need at least 2" in body["reason"].lower()


@pytest.mark.asyncio
async def test_lock_succeeds_when_two_corrections_agree(client, db_session):
    h, pid = await _auth_and_project(client, email="lk2@lk.com")
    # set schema first
    payload = {
        "schema": [
            {"name": "shop_name", "type": "string", "description": "d"},
            {"name": "total", "type": "number", "description": "d"},
        ],
        "global_notes": "",
        "model_id": "x",
    }
    await client.patch(f"/api/v1/projects/{pid}/schema", json=payload, headers=h)

    # seed two saved Annotations directly into DB whose key sets agree
    user_id = (await db_session.execute(select(User).order_by(User.id).limit(1))).scalar_one().id
    for fname in ("a.pdf", "b.pdf"):
        d = Document(
            project_id=pid,
            filename=fname,
            file_path=f"/tmp/{fname}",
            mime_type="application/pdf",
            page_count=1,
            byte_size=10,
            uploaded_by=user_id,
        )
        db_session.add(d)
        await db_session.flush()
        db_session.add(
            Annotation(
                document_id=d.id,
                output=[{"shop_name": "X", "total": 1}],
                role=AnnotationRole.NONE.value,
                status=AnnotationStatus.SAVED.value,
                created_by=user_id,
                last_modified_by=user_id,
            )
        )
    await db_session.commit()

    status = await client.get(f"/api/v1/projects/{pid}/lock-status", headers=h)
    assert status.json()["can_lock"] is True

    locked = await client.post(f"/api/v1/projects/{pid}/lock", headers=h)
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
