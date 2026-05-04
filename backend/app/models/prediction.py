from enum import Enum

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PredictionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success','partial','failed')", name="ck_prediction_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    project_version_id: Mapped[int | None] = mapped_column(nullable=True)  # FK in R3
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    output: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    per_field_confidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Field-level evidence: { entity_idx: { field_name: { page?, quote?, rationale?, source_text_hash? } } }
    # Spec §3.2 hard rule: NO bbox / coordinates / polygons / regions / spans.
    per_field_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
