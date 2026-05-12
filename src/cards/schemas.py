from pydantic import BaseModel, Field, field_validator

from bson import ObjectId


class CardCreate(BaseModel):
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool = True


class CardUpdate(BaseModel):
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool | None = None


class CardResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    owner_id: str
    slug: str
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool
    qr_code_url: str | None = None
    view_count: int = 0

    model_config = {"populate_by_name": True, "from_attributes": True}

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
