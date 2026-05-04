import pytest

from app.engine.extract import extract_document
from app.engine.provider import ExtractionResult
from app.engine.providers import get_provider_dep
from app.engine.providers.fake import FakeProvider
from app.models.document import Document, DocumentStatus
from app.models.prediction import Prediction


@pytest.mark.asyncio
async def test_prediction_can_store_field_level_evidence(db_session):
    pred = Prediction(
        document_id=1,
        project_version_id=2,
        model_id="test-model",
        prompt_hash="abc",
        output=[{"total": 1234}],
        per_field_confidence={"0": {"total": "up"}},
        per_field_evidence={
            "0": {
                "total": {
                    "page": 1,
                    "quote": "Total ¥1,234",
                    "rationale": "Used the tax-included total line",
                }
            }
        },
        status="success",
    )
    db_session.add(pred)
    await db_session.flush()
    await db_session.refresh(pred)

    assert pred.per_field_evidence["0"]["total"]["quote"] == "Total ¥1,234"
    # Hard rule: no bbox / coordinates / spans / regions in evidence shape.
    cell = pred.per_field_evidence["0"]["total"]
    for forbidden in ("bbox", "coordinates", "polygon", "region", "span"):
        assert forbidden not in cell


class _EvidenceProvider(FakeProvider):
    """FakeProvider that emits field-level evidence on the ExtractionResult."""

    def __init__(self, *, output, evidence):
        super().__init__(canned=[])
        self._output = output
        self._evidence = evidence

    async def extract(self, request, *, file_bytes, mime_type):
        self.calls.append(request)
        return ExtractionResult(
            output=self._output,
            tokens_used=0,
            latency_ms=0,
            raw_response={"per_field_evidence": self._evidence},
        )


@pytest.mark.asyncio
async def test_extract_persists_evidence_when_provider_supplies_it(
    app, db_session, tmp_path, monkeypatch
):
    """If the provider returns per_field_evidence, the engine persists it."""
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.project_version import ProjectVersion, VersionSource
    from app.models.user import User
    from app.models.workspace import Workspace

    u = User(email="ev@ev.com", password_hash="x")
    db_session.add(u)
    await db_session.flush()
    w = Workspace(name="W", owner_id=u.id)
    db_session.add(w)
    await db_session.flush()
    proj = Project(workspace_id=w.id, name="P", created_by=u.id)
    db_session.add(proj)
    await db_session.flush()
    v = ProjectVersion(
        project_id=proj.id,
        version_number=1,
        schema_snapshot=[
            {"name": "total", "type": "number", "description": "total amount"}
        ],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=u.id,
    )
    db_session.add(v)
    await db_session.flush()
    proj.active_version_id = v.id
    await db_session.flush()

    file_path = tmp_path / "x.pdf"
    file_path.write_bytes(b"PDF")
    doc = Document(
        project_id=proj.id,
        filename="x.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        page_count=1,
        byte_size=3,
        uploaded_by=u.id,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    evidence = {
        "0": {
            "total": {
                "page": 1,
                "quote": "Total ¥1,234",
                "rationale": "tax-included total",
            }
        }
    }
    provider = _EvidenceProvider(output=[{"total": 1234}], evidence=evidence)

    pred = await extract_document(doc.id, session=db_session, provider=provider)

    assert pred.status == "success"
    assert pred.per_field_evidence == evidence


@pytest.mark.asyncio
async def test_extract_leaves_evidence_none_when_provider_omits(
    app, db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    from app.models.project import Project
    from app.models.project_version import ProjectVersion, VersionSource
    from app.models.user import User
    from app.models.workspace import Workspace

    u = User(email="ev2@ev.com", password_hash="x")
    db_session.add(u)
    await db_session.flush()
    w = Workspace(name="W", owner_id=u.id)
    db_session.add(w)
    await db_session.flush()
    proj = Project(workspace_id=w.id, name="P", created_by=u.id)
    db_session.add(proj)
    await db_session.flush()
    v = ProjectVersion(
        project_id=proj.id,
        version_number=1,
        schema_snapshot=[{"name": "total", "type": "number", "description": "total"}],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=u.id,
    )
    db_session.add(v)
    await db_session.flush()
    proj.active_version_id = v.id
    await db_session.flush()

    file_path = tmp_path / "y.pdf"
    file_path.write_bytes(b"PDF")
    doc = Document(
        project_id=proj.id,
        filename="y.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        page_count=1,
        byte_size=3,
        uploaded_by=u.id,
        status=DocumentStatus.UPLOADED.value,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    provider = FakeProvider(canned=[[{"total": 10}]])
    pred = await extract_document(doc.id, session=db_session, provider=provider)

    assert pred.status == "success"
    assert pred.per_field_evidence is None
