from enum import Enum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    ERRORED = "errored"
    ARCHIVED = "archived"


class DocumentSource(str, Enum):
    LAB = "lab"
    PUBLIC_API = "public_api"


_VALID_STATUSES = ",".join(f"'{s.value}'" for s in DocumentStatus)
_VALID_SOURCES = ",".join(f"'{s.value}'" for s in DocumentSource)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN ({_VALID_STATUSES})", name="ck_document_status"),
        CheckConstraint(f"source IN ({_VALID_SOURCES})", name="ck_document_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentStatus.UPLOADED.value
    )
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DocumentSource.LAB.value,
        index=True,
    )
