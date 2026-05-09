# from pydantic import BaseModel


# class TagCreate(BaseModel):
#     name: str
#     color: str = "#6366f1"


# class TagUpdate(BaseModel):
#     name: str | None = None
#     color: str | None = None


# class TagResponse(BaseModel):
#     id: str
#     owner_id: str
#     name: str
#     color: str
#     contact_count: int = 0


"""
src/tags/schemas.py
-------------------
Pydantic v2 schemas cho Tags module.
"""

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# TagCreate — payload khi tạo tag mới
# ---------------------------------------------------------------------------

class TagCreate(BaseModel):
    # name bắt buộc, giới hạn 1–50 ký tự để tránh spam
    name: str = Field(..., min_length=1, max_length=50)

    # color mặc định là màu tím Cardly, phải đúng định dạng hex (#RRGGBB)
    color: str = Field(default="#7F77DD", pattern=r"^#[0-9A-Fa-f]{6}$")

    # source phân biệt tag do user tạo hay do hệ thống tự sinh (OCR/AI)
    source: Literal["auto", "manual"] = "manual"


# ---------------------------------------------------------------------------
# TagUpdate — payload khi update tag, tất cả field đều optional
# ---------------------------------------------------------------------------

class TagUpdate(BaseModel):
    # None = không cập nhật field đó → dùng exclude_none khi build $set
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


# ---------------------------------------------------------------------------
# TagResponse — shape trả về cho client
# ---------------------------------------------------------------------------

class TagResponse(BaseModel):
    # Đổi tên _id → id vì client không cần biết MongoDB dùng underscore
    id: str = Field(validation_alias="_id")
    owner_id: str
    name: str
    color: str
    source: str
    created_at: datetime

    model_config = {
        # populate_by_name=True cho phép khởi tạo bằng "id" hoặc "_id" đều được
        "populate_by_name": True,
        # from_attributes=True để dùng TagResponse.model_validate(dict_from_mongo)
        "from_attributes": True,
    }

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid_to_str(cls, v):
        # MongoDB trả về ObjectId, Pydantic cần str — convert tại đây
        # thay vì convert rải rác ở service/router
        if isinstance(v, ObjectId):
            return str(v)
        return v