from enum import Enum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VersionSource(str, Enum):
    INITIAL = "initial"
    USER_EDIT = "user_edit"
    AUTO_RESEARCH = "auto_research"


class ProjectVersion(Base, TimestampMixin):
    __tablename__ = "project_versions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('initial','user_edit','auto_research')",
            name="ck_project_version_source",
        ),
        UniqueConstraint(
            "project_id", "version_number", name="uq_project_version_number"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    schema_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    global_notes_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_id_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    counterexample_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    locked: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
