import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TagCreate(BaseModel):
    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 50:
            raise ValueError("Tag name must be 1–50 characters")
        return v

    @field_validator("color")
    @classmethod
    def color_hex(cls, v: str | None) -> str | None:
        if v and not _HEX_COLOR_RE.match(v):
            raise ValueError("Color must be a valid hex color (#RRGGBB)")
        return v


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 50:
                raise ValueError("Tag name must be 1–50 characters")
        return v

    @field_validator("color")
    @classmethod
    def color_hex(cls, v: str | None) -> str | None:
        if v and not _HEX_COLOR_RE.match(v):
            raise ValueError("Color must be a valid hex color (#RRGGBB)")
        return v


class TagResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    color: str | None = None
    source: str
    created_at: datetime
