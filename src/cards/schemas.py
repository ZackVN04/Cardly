import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")


def _validate_slug(v: str) -> str:
    if not _SLUG_RE.match(v):
        raise ValueError("Slug must be 3–30 chars, lowercase alphanumeric/hyphens, not starting with hyphen")
    return v


class CardLinks(BaseModel):
    phone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    zalo: str | None = None
    linkedin: str | None = None
    website: str | None = None


class DigitalCardCreate(BaseModel):
    slug: str
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: CardLinks = CardLinks()
    is_public: bool = True

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str) -> str:
        return _validate_slug(v)


class DigitalCardUpdate(BaseModel):
    slug: str | None = None
    display_name: str | None = None
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] | None = None
    links: CardLinks | None = None
    is_public: bool | None = None

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str | None) -> str | None:
        return _validate_slug(v) if v is not None else v


class DigitalCardResponse(BaseModel):
    id: str
    user_id: str
    slug: str
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: CardLinks = CardLinks()
    qr_code_url: str | None = None
    is_public: bool
    view_count: int = 0
    created_at: datetime
    updated_at: datetime


class PublicCardResponse(BaseModel):
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: CardLinks = CardLinks()
    qr_code_url: str | None = None
