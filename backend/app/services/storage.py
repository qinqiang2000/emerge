import asyncio
import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.settings import settings


@dataclass
class StoredFile:
    file_path: str
    filename: str
    mime_type: str
    byte_size: int


def _sanitize(name: str) -> str:
    name = os.path.basename(name)  # strip path separators
    return name.replace("\0", "")[:255] or "unnamed"


async def save_upload(file: UploadFile, *, project_id: int) -> StoredFile:
    safe = _sanitize(file.filename or "unnamed")
    target_dir = Path(settings.storage_root) / "projects" / str(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}-{safe}"
    target_path = target_dir / stored_name

    def _write_sync(data: bytes) -> int:
        with open(target_path, "wb") as fh:
            return fh.write(data)

    raw = await file.read()
    size = await asyncio.to_thread(_write_sync, raw)
    return StoredFile(
        file_path=str(target_path),
        filename=safe,
        mime_type=file.content_type or mimetypes.guess_type(safe)[0] or "application/octet-stream",
        byte_size=size,
    )
