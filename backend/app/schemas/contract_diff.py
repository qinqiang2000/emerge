from typing import Any, Literal

from pydantic import BaseModel


class ContractDiffItem(BaseModel):
    kind: str
    severity: Literal["breaking", "non_breaking"]
    field_name: str | None = None
    before: Any = None
    after: Any = None
    message: str


class ContractDiffOut(BaseModel):
    from_version_id: int | None = None
    to_version_id: int | None = None
    has_breaking_changes: bool
    items: list[ContractDiffItem]
