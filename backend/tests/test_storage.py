import io

import pytest
from fastapi import UploadFile

from app.services.storage import save_upload


@pytest.mark.asyncio
async def test_save_upload_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    f = UploadFile(filename="my.pdf", file=io.BytesIO(b"PDFDATA"))
    rec = await save_upload(f, project_id=42)
    assert rec.byte_size == 7
    assert rec.mime_type == "application/pdf"
    with open(rec.file_path, "rb") as fh:
        assert fh.read() == b"PDFDATA"
    assert "/projects/42/" in rec.file_path


@pytest.mark.asyncio
async def test_save_upload_strips_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    f = UploadFile(filename="../../etc/passwd", file=io.BytesIO(b"x"))
    rec = await save_upload(f, project_id=1)
    assert ".." not in rec.file_path
    assert "passwd" in rec.filename
