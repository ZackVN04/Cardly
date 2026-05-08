from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class ActivityLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict | None = None
    created_at: datetime


ActivityLogList = PaginatedResponse[ActivityLogResponse]
