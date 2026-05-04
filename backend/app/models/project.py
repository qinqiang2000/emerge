from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "api_code", name="uq_project_workspace_api_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    project_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="extraction", server_default="extraction"
    )
    template_id: Mapped[int | None] = mapped_column(nullable=True)  # FK added in R7
    active_version_id: Mapped[int | None] = mapped_column(nullable=True)  # FK added in R3
    # Public API serves this version; spec §7.2: editing/AutoResearch never auto-promote.
    published_version_id: Mapped[int | None] = mapped_column(nullable=True)
    api_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
