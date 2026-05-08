from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse
from src.contacts.schemas import ContactResponse


class EventCreate(BaseModel):
    name: str
    location: str | None = None
    event_date: datetime | None = None
    description: str | None = None


class EventUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    event_date: datetime | None = None
    description: str | None = None


class EventResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    location: str | None = None
    event_date: datetime | None = None
    description: str | None = None
    created_at: datetime


class EventWithContacts(EventResponse):
    contacts: PaginatedResponse[ContactResponse]
