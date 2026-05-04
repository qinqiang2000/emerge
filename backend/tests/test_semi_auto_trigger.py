import pytest

from app.models.workspace_setting import WorkspaceSetting
from app.services.autoresearch.trigger import KEY, maybe_should_trigger


@pytest.mark.asyncio
async def test_returns_false_when_setting_unset(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "tr@tr.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "tr@tr.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    assert await maybe_should_trigger(session=db_session, project_id=pid) is False


@pytest.mark.asyncio
async def test_returns_true_when_threshold_crossed(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "tr2@tr.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "tr2@tr.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]

    from sqlalchemy import select

    from app.models.project import Project

    project = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    db_session.add(WorkspaceSetting(workspace_id=project.workspace_id, key=KEY, value="2"))
    await db_session.commit()

    # seed 3 counterexamples
    from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
    from app.models.document import Document
    from app.models.user import User

    user_id = (await db_session.execute(select(User))).scalar_one().id
    d = Document(
        project_id=pid,
        filename="x",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user_id,
    )
    db_session.add(d)
    await db_session.flush()
    for _ in range(3):
        db_session.add(
            Annotation(
                document_id=d.id,
                output=[{"a": 1}],
                role=AnnotationRole.COUNTEREXAMPLE.value,
                status=AnnotationStatus.SAVED.value,
                created_by=user_id,
                last_modified_by=user_id,
            )
        )
    await db_session.commit()

    assert await maybe_should_trigger(session=db_session, project_id=pid) is True
