"""
src/events/schemas.py
---------------------
Pydantic v2 schemas cho Events module.
"""

from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# EventCreate — payload khi tạo event mới
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # tên bắt buộc, giới hạn độ dài
    location: str | None = None                           # địa điểm tùy chọn
    event_date: datetime                                  # bắt buộc — dùng để sort và hiển thị
    description: str | None = None                        # mô tả tùy chọn


# ---------------------------------------------------------------------------
# EventUpdate — tất cả field optional, chỉ update field được gửi lên
# ---------------------------------------------------------------------------

class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = None
    event_date: datetime | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# EventResponse — shape trả về cho client
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    id: str = Field(validation_alias="_id")   # _id MongoDB → id client-friendly
    owner_id: str
    name: str
    location: str | None
    event_date: datetime
    description: str | None
    created_at: datetime

    model_config = {
        "populate_by_name": True,   # accept cả "id" và "_id" khi khởi tạo
        "from_attributes": True,
    }

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        # MongoDB trả ObjectId — convert sang str để JSON-serializable
        if isinstance(v, ObjectId):
            return str(v)
        return v


# ---------------------------------------------------------------------------
# ContactSummary — shape gọn cho contact khi nhúng vào EventWithContacts
# Chỉ lấy 3 field cần thiết, tránh over-fetch toàn bộ contact document
# ---------------------------------------------------------------------------

class ContactSummary(BaseModel):
    id: str = Field(validation_alias="_id")
    full_name: str
    company: str | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


# ---------------------------------------------------------------------------
# EventWithContacts — EventResponse + danh sách contacts đã phân trang
# ---------------------------------------------------------------------------

class EventWithContacts(EventResponse):
    contacts: list[ContactSummary] = []    # slice đã phân trang từ $lookup
    contacts_total: int = 0               # tổng số contacts thực (không phải len slice)