import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_API_CODE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-))*[a-z0-9]$|^[a-z0-9]$")


class PublishIn(BaseModel):
    api_code: str

    @field_validator("api_code")
    @classmethod
    def _check(cls, v: str) -> str:
        if not _API_CODE.match(v):
            raise ValueError("api_code must be lowercase alphanumeric with hyphens, 1-64 chars, no consecutive hyphens")
        return v


class ApiKeyIn(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=128)


class ApiKeyOnceOut(BaseModel):
    id: int
    prefix: str
    name: str
    key: str  # plaintext, returned only on create


class ApiKeyOut(BaseModel):
    id: int
    prefix: str
    name: str
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
