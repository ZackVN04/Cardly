from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from src.core.pagination import PaginatedResponse


# ---------------------------------------------------------------------------
# ScanExtractedData — kết quả OCR trích xuất từ ảnh danh thiếp
# Dùng trong ScanResponse.extracted_data và ScanPatch.extracted_data
# ---------------------------------------------------------------------------

class ScanExtractedData(BaseModel):
    full_name: str | None = None
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    qr_code: str | None = None  # URL trong QR nếu có trên danh thiếp


# ---------------------------------------------------------------------------
# PatchExtractedData — 9 field spec cho phép user sửa qua PATCH
# Tách riêng khỏi ScanExtractedData vì spec không cho edit qr_code
# ---------------------------------------------------------------------------

class PatchExtractedData(BaseModel):
    full_name: str | None = None
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None


# ---------------------------------------------------------------------------
# ScanPatch — PATCH /{scanId}: sửa raw_text hoặc extracted_data trước confirm
# Status KHÔNG thay đổi qua endpoint này
# ---------------------------------------------------------------------------

class ScanPatch(BaseModel):
    raw_text: str | None = None
    extracted_data: PatchExtractedData | None = None


# ---------------------------------------------------------------------------
# ConfirmedData — nested trong ConfirmScanRequest
# full_name bắt buộc; tách riêng khỏi ScanExtractedData vì full_name ở đây required
# ---------------------------------------------------------------------------

class ConfirmedData(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None


# ---------------------------------------------------------------------------
# ConfirmScanRequest — POST /{scanId}/confirm
# confirmed_data: thông tin cuối user xác nhận để tạo contact
# notes, tag_ids, event_id: gắn context cho contact được tạo
# ---------------------------------------------------------------------------

class ConfirmScanRequest(BaseModel):
    confirmed_data: ConfirmedData
    notes: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None


# ---------------------------------------------------------------------------
# ScanResponse — shape trả về client cho GET /, GET /{id}, PATCH /{id}
# ---------------------------------------------------------------------------

class ScanResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    owner_id: str
    event_id: str | None = None
    image_url: str | None = None
    status: Literal["pending", "processing", "completed", "confirmed", "failed"]
    raw_text: str | None = None
    extracted_data: ScanExtractedData | None = None
    confidence_score: float | None = None
    scanned_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def coerce_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

    @field_validator("event_id", mode="before")
    @classmethod
    def coerce_optional_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


ScanList = PaginatedResponse[ScanResponse]
