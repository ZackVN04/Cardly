from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class ScanResponse(BaseModel):
    id: str
    owner_id: str
    image_url: str
    status: str
    extracted_data: dict | None = None
    contact_id: str | None = None
    created_at: datetime


ScanListResponse = PaginatedResponse[ScanResponse]
