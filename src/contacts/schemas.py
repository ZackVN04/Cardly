from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class ContactCreate(BaseModel):
    full_name: str
    company: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    notes: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None


class ContactUpdate(BaseModel):
    full_name: str | None = None
    company: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    notes: str | None = None


class ContactResponse(BaseModel):
    id: str
    owner_id: str
    full_name: str
    company: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    notes: str | None = None
    avatar_url: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None


ContactListResponse = PaginatedResponse[ContactResponse]
