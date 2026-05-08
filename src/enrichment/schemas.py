from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class EnrichmentResponse(BaseModel):
    id: str
    contact_id: str
    owner_id: str
    status: str
    enriched_data: dict | None = None
    created_at: datetime


EnrichmentListResponse = PaginatedResponse[EnrichmentResponse]
