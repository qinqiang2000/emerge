from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AutoResearchStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EARLY_STOPPED = "early_stopped"
    MANUAL_STOPPED = "manual_stopped"


class TerminationReason(str, Enum):
    THRESHOLD_MET = "threshold_met"
    MAX_TURN = "max_turn"
    NO_IMPROVEMENT = "no_improvement"
    MANUAL_STOP = "manual_stop"
    ERROR = "error"


class AutoResearchRun(Base, TimestampMixin):
    __tablename__ = "auto_research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed','early_stopped','manual_stopped')",
            name="ck_auto_research_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    starting_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )
    output_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )

    judge_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    researcher_model_id: Mapped[str] = mapped_column(String(128), nullable=False)

    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    turn_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    termination_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
