from datetime import datetime

from pydantic import BaseModel, EmailStr

from src.core.pagination import PaginatedResponse


class ContactCreate(BaseModel):
    full_name: str
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    notes: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None


class ContactUpdate(BaseModel):
    full_name: str | None = None
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    notes: str | None = None
    event_id: str | None = None


class ContactResponse(BaseModel):
    id: str
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


ContactListResponse = PaginatedResponse[ContactResponse]
