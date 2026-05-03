from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AnnotationRole(str, Enum):
    COUNTEREXAMPLE = "counterexample"
    NONE = "none"


class AnnotationStatus(str, Enum):
    DRAFT = "draft"
    SAVED = "saved"
    CANCELLED = "cancelled"


class Annotation(Base, TimestampMixin):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('counterexample','none')", name="ck_annotation_role"
        ),
        CheckConstraint(
            "status IN ('draft','saved','cancelled')", name="ck_annotation_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    parent_prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("predictions.id"), nullable=True
    )

    output: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AnnotationStatus.SAVED.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
