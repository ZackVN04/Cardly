import asyncio
import base64
import json
import logging
import re

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.config import settings

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-1.5-flash:generateContent"
)

_PROMPT = """\
Extract contact information from this business card image.
The card may be in Vietnamese, English, or both.

Return ONLY a valid JSON object with exactly these keys (use null for any missing field):
{
  "full_name": string or null,
  "position": string or null,
  "company": string or null,
  "phone": string or null,
  "email": string or null,
  "website": string or null,
  "linkedin_url": string or null,
  "facebook_url": string or null,
  "address": string or null,
  "qr_code": string or null
}

Rules:
- full_name: full person name as printed (keep Vietnamese diacritics)
- position: job title / chức danh
- phone: preserve original format including country code
- qr_code: decoded URL/text if a QR code is visible on the card, otherwise null
- Return ONLY the JSON object — no markdown fences, no explanation.\
"""

_KEY_FIELDS = ("full_name", "phone", "email", "company", "position", "address", "website")

_ALLOWED_FIELDS = {
    "full_name", "position", "company", "phone", "email",
    "website", "linkedin_url", "facebook_url", "address", "qr_code",
}


async def _fetch_image(image_url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(image_url)
        r.raise_for_status()
    mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        mime = "image/jpeg"
    return r.content, mime


async def _call_gemini(image_bytes: bytes, mime_type: str) -> str:
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode(),
                    }
                },
                {"text": _PROMPT},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            _GEMINI_URL,
            params={"key": settings.GEMINI_API_KEY},
            json=payload,
        )
        r.raise_for_status()
    body = r.json()
    return body["candidates"][0]["content"]["parts"][0]["text"]


def parse_ocr_response(raw_text: str) -> dict:
    """Parse Gemini OCR text response into a cleaned dict."""
    text = raw_text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in data.items() if k in _ALLOWED_FIELDS and v is not None}


def _compute_confidence(extracted: dict) -> float:
    """Score 0.0–1.0 dựa trên số key fields trích xuất được."""
    filled = sum(1 for f in _KEY_FIELDS if extracted.get(f))
    return round(filled / len(_KEY_FIELDS), 2)


def mock_extract() -> dict:
    """Mock extracted data cho ENVIRONMENT='test' — không gọi Gemini thật."""
    return {
        "full_name": "Nguyen Van A",
        "position": "CEO",
        "company": "TechCorp",
        "phone": "0901234567",
        "email": "a@techcorp.com",
        "website": "techcorp.com",
        "address": "123 Nguyen Hue, Ho Chi Minh City",
    }


async def extract_card_data(image_url: str) -> tuple[dict, str]:
    """Fetch image từ URL và chạy Gemini OCR. Returns (extracted_dict, raw_text)."""
    image_bytes, mime_type = await _fetch_image(image_url)
    raw_text = await _call_gemini(image_bytes, mime_type)
    return parse_ocr_response(raw_text), raw_text


async def run_ocr(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    image_url: str,
) -> None:
    """Background task: chạy OCR và cập nhật scan document."""
    try:
        if settings.ENVIRONMENT == "test":
            extracted = mock_extract()
            raw_text = "mock_ocr_output"
        else:
            extracted, raw_text = await extract_card_data(image_url)

        confidence_score = _compute_confidence(extracted)

        await db["business_card_scans"].update_one(
            {"_id": scan_id},
            {"$set": {
                "status": "completed",
                "raw_text": raw_text,
                "extracted_data": extracted,
                "confidence_score": confidence_score,
            }},
        )
    except Exception as exc:
        logger.error("OCR failed for scan %s: %s", scan_id, exc)
        await db["business_card_scans"].update_one(
            {"_id": scan_id},
            {"$set": {"status": "failed"}},
        )
