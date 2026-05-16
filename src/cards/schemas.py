from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{2,29}$"


class CardLinks(BaseModel):
    phone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    zalo: str | None = None
    linkedin: str | None = None
    website: str | None = None


class DigitalCardCreate(BaseModel):
    slug: str = Field(..., pattern=SLUG_PATTERN)
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: CardLinks | None = None
    is_public: bool = True


class DigitalCardUpdate(BaseModel):
    slug: str | None = Field(None, pattern=SLUG_PATTERN)
    display_name: str | None = None
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] | None = None
    links: CardLinks | None = None
    is_public: bool | None = None


class DigitalCardResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    user_id: str
    slug: str
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: dict | None = None
    qr_code_url: str | None = None
    is_public: bool
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


class PublicCardResponse(BaseModel):
    display_name: str
    title: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    highlights: list[str] = []
    links: dict | None = None
    qr_code_url: str | None = None
