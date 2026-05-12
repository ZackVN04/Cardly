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


async def _fetch_image(image_url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(image_url)
        r.raise_for_status()
    mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        mime = "image/jpeg"
    return r.content, mime


def _parse_response(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    allowed = {
        "full_name", "position", "company", "phone", "email",
        "website", "linkedin_url", "facebook_url", "address", "qr_code",
    }
    return {k: v for k, v in data.items() if k in allowed and v is not None}


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


async def run_ocr(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    image_url: str,
) -> None:
    """Background task: call Gemini Vision OCR and update the scan document."""
    try:
        image_bytes, mime_type = await _fetch_image(image_url)
        raw_text = await _call_gemini(image_bytes, mime_type)
        extracted = _parse_response(raw_text)
        confidence_score = 0.9 if extracted.get("full_name") else 0.4

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
