from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class ActivityLogResponse(BaseModel):
    id: str
    contact_id: str
    owner_id: str
    action: str
    source: str
    changed_fields: list[str] = []
    previous_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    created_at: datetime


ActivityLogList = PaginatedResponse[ActivityLogResponse]
