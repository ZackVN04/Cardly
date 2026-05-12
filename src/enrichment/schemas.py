from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from src.core.pagination import PaginatedResponse


class EnrichmentResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    contact_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    brief: str | None = None
    keywords: list[str] = []
    highlights: list[str] = []
    linkedin_data: dict | None = None
    facebook_data: dict | None = None
    website_data: dict | None = None
    source: Literal["gemini", "vertex_ai", "manual"] | None = None
    enriched_at: datetime | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}

    @field_validator("id", "contact_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


class EnrichmentUpdate(BaseModel):
    brief: str | None = None
    keywords: list[str] | None = None
    highlights: list[str] | None = None
    linkedin_data: dict | None = None
    facebook_data: dict | None = None
    website_data: dict | None = None


EnrichmentList = PaginatedResponse[EnrichmentResponse]
