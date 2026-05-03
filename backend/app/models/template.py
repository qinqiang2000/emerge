from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Template(Base, TimestampMixin):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "name", "version", name="uq_template_workspace_name_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )  # NULL for builtins
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    global_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
