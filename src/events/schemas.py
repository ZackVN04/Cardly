from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class EventCreate(BaseModel):
    name: str
    description: str | None = None
    date: datetime | None = None
    location: str | None = None


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date: datetime | None = None
    location: str | None = None


class EventResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    description: str | None = None
    date: datetime | None = None
    location: str | None = None
    contact_count: int = 0


EventListResponse = PaginatedResponse[EventResponse]
