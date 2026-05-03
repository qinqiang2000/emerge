from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JudgeCalibration(Base, TimestampMixin):
    __tablename__ = "judge_calibrations"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "judge_model_version", name="uq_calibration_project_judge"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    judge_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    tp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
