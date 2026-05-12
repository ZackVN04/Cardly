from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from src.core.pagination import PaginatedResponse


class ContactCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    notes: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None
    scan_id: str | None = None


class ContactUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    notes: str | None = None
    event_id: str | None = None


class AddTagRequest(BaseModel):
    tag_id: str


class ContactResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    owner_id: str
    scan_id: str | None = None
    event_id: str | None = None
    tag_ids: list[str] = []
    full_name: str
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

    @field_validator("scan_id", "event_id", mode="before")
    @classmethod
    def coerce_optional_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

    @field_validator("tag_ids", mode="before")
    @classmethod
    def coerce_tag_ids(cls, v):
        if isinstance(v, list):
            return [str(i) if isinstance(i, ObjectId) else i for i in v]
        return v


ContactListResponse = PaginatedResponse[ContactResponse]
