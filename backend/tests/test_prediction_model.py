import pytest

from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_prediction_persists_with_json_output(db_session):
    user = User(email="pr@pr.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    pred = Prediction(
        document_id=d.id,
        model_id="claude-opus-4-7",
        prompt_hash="abc",
        output=[{"shop_name": "X"}],
        per_field_confidence={},
        tokens_used=100,
        latency_ms=200,
        cost_estimate=0.0,
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()
    await db_session.refresh(pred)
    assert pred.id is not None
    assert pred.output == [{"shop_name": "X"}]
