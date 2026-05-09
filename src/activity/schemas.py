# from datetime import datetime

# from pydantic import BaseModel

# from src.core.pagination import PaginatedResponse


# class ActivityLogResponse(BaseModel):
#     id: str
#     user_id: str
#     action: str
#     entity_type: str
#     entity_id: str
#     detail: dict | None = None
#     created_at: datetime


# ActivityLogList = PaginatedResponse[ActivityLogResponse]
"""
src/activity/schemas.py
-----------------------
Pydantic v2 schemas cho Activity module.

Schema phải khớp chính xác với collection contact_activity_logs:
{
    "_id": ObjectId,
    "contact_id": ObjectId,
    "owner_id": ObjectId,
    "action": str,           # "created"|"updated"|"enriched"|"tagged"|"deleted"
    "source": str,           # "scan"|"manual"|"enrichment"|"user_edit"
    "changed_fields": list[str],
    "previous_values": dict,
    "new_values": dict,
    "created_at": datetime
}
"""

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from src.core.pagination import PaginatedResponse


class ActivityLogResponse(BaseModel):
    # _id MongoDB → id client-friendly, alias để model_validate từ raw dict hoạt động
    id: str = Field(alias="_id")

    # contact_id và owner_id là ObjectId trong DB — convert sang str cho JSON
    contact_id: str
    owner_id: str

    # action và source dùng Literal để tự document và validate chặt
    action: Literal["created", "updated", "enriched", "tagged", "deleted"]
    source: Literal["scan", "manual", "enrichment", "user_edit"]

    # changed_fields có thể rỗng nếu là log "created" hoặc "deleted"
    changed_fields: list[str] = []

    # previous/new values là dict tự do — không ép schema cứng vì mỗi module
    # log các field khác nhau (tags log name/color, events log name/event_date...)
    previous_values: dict = {}
    new_values: dict = {}

    created_at: datetime

    model_config = {
        "populate_by_name": True,   # accept cả "_id" và "id" khi khởi tạo
        "from_attributes": True,
    }

    @field_validator("id", "contact_id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        # MongoDB trả ObjectId — convert sang str để JSON-serializable
        # mode="before" chạy trước type check của Pydantic
        if isinstance(v, ObjectId):
            return str(v)
        return v


# Alias tiện dùng — type đầy đủ cho router return type hint
ActivityLogList = PaginatedResponse[ActivityLogResponse]