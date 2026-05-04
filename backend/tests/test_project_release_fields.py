import pytest
from pydantic import ValidationError

from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.project import ProjectIn, ProjectOut


@pytest.mark.asyncio
async def test_project_defaults_to_extraction_and_unpublished(db_session):
    u = User(email="rel@rel.com", password_hash="x")
    db_session.add(u)
    await db_session.flush()
    w = Workspace(name="W", owner_id=u.id)
    db_session.add(w)
    await db_session.flush()
    p = Project(workspace_id=w.id, name="P", created_by=u.id)
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)

    assert p.project_type == "extraction"
    assert p.published_version_id is None


def test_project_in_accepts_only_extraction():
    assert ProjectIn(name="P").project_type == "extraction"
    assert ProjectIn(name="P", project_type="extraction").project_type == "extraction"
    with pytest.raises(ValidationError):
        ProjectIn(name="P", project_type="matching")


def test_project_out_exposes_release_fields():
    p = Project(
        id=1,
        workspace_id=2,
        name="P",
        created_by=3,
        project_type="extraction",
        active_version_id=10,
        published_version_id=9,
    )
    # created_at is set by TimestampMixin only after flush; supply manually for unit test.
    from datetime import UTC, datetime
    p.created_at = datetime.now(tz=UTC)
    out = ProjectOut.model_validate(p)
    assert out.project_type == "extraction"
    assert out.active_version_id == 10
    assert out.published_version_id == 9
