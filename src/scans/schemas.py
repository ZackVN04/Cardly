from datetime import datetime

from pydantic import BaseModel, field_validator

from src.core.pagination import PaginatedResponse


class ExtractedData(BaseModel):
    full_name: str | None = None
    position: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    facebook_url: str | None = None
    address: str | None = None
    qr_code: str | None = None


class ScanCreate(BaseModel):
    event_id: str | None = None


class ScanResponse(BaseModel):
    id: str
    owner_id: str
    image_url: str
    raw_text: str | None = None
    status: str
    confidence_score: float | None = None
    extracted_data: ExtractedData | None = None
    scanned_at: datetime


class ScanPatch(BaseModel):
    raw_text: str | None = None
    extracted_data: ExtractedData | None = None


class ConfirmScanRequest(BaseModel):
    confirmed_data: ExtractedData
    notes: str | None = None
    tag_ids: list[str] = []
    event_id: str | None = None

    @field_validator("confirmed_data")
    @classmethod
    def full_name_required(cls, v: ExtractedData) -> ExtractedData:
        if not v.full_name:
            raise ValueError("confirmed_data.full_name is required")
        return v


ScanList = PaginatedResponse[ScanResponse]
