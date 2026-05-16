import io
import logging
from datetime import datetime

import qrcode
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from src.cards.exceptions import CardNotFound, SlugAlreadyTaken, UserAlreadyHasCard
from src.cards.schemas import DigitalCardCreate, DigitalCardUpdate
from src.uploads.storage_client import upload_to_gcs

logger = logging.getLogger(__name__)

_QR_BASE_URL = "https://cardly.me"


# ---------------------------------------------------------------------------
# generate_qr — build QR PNG in memory and upload to GCS
# ---------------------------------------------------------------------------

async def generate_qr(slug: str) -> str | None:
    url = f"{_QR_BASE_URL}/{slug}"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)

    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")

    try:
        return await upload_to_gcs(buf.getvalue(), f"qr_codes/{slug}.png", "image/png")
    except Exception:
        logger.warning("QR upload failed for slug=%s — qr_code_url will be None", slug)
        return None


# ---------------------------------------------------------------------------
# get_my_card
# ---------------------------------------------------------------------------

async def get_my_card(db: AsyncIOMotorDatabase, user_id: ObjectId) -> dict:
    card = await db["digital_cards"].find_one({"user_id": user_id})
    if not card:
        raise CardNotFound()
    return card


# ---------------------------------------------------------------------------
# create_card — validate slug uniqueness, generate QR, insert
# ---------------------------------------------------------------------------

async def create_card(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    data: DigitalCardCreate,
) -> dict:
    if await db["digital_cards"].find_one({"user_id": user_id}):
        raise UserAlreadyHasCard()

    now = datetime.utcnow()
    qr_code_url = await generate_qr(data.slug)

    doc = {
        "user_id": user_id,
        "slug": data.slug,
        "display_name": data.display_name,
        "title": data.title,
        "company": data.company,
        "avatar_url": data.avatar_url,
        "bio": data.bio,
        "highlights": data.highlights,
        "links": data.links.model_dump() if data.links else None,
        "qr_code_url": qr_code_url,
        "is_public": data.is_public,
        "view_count": 0,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await db["digital_cards"].insert_one(doc)
    except DuplicateKeyError:
        raise SlugAlreadyTaken()

    return await db["digital_cards"].find_one({"_id": result.inserted_id})


# ---------------------------------------------------------------------------
# update_card — regenerate QR if slug changes, catch slug conflicts
# ---------------------------------------------------------------------------

async def update_card(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    data: DigitalCardUpdate,
) -> dict:
    card = await db["digital_cards"].find_one({"user_id": user_id})
    if not card:
        raise CardNotFound()

    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        return card

    # Serialize nested CardLinks model → plain dict for MongoDB
    if "links" in update_fields and data.links is not None:
        update_fields["links"] = data.links.model_dump()

    # Regenerate QR only when slug actually changes
    new_slug = update_fields.get("slug")
    if new_slug and new_slug != card["slug"]:
        update_fields["qr_code_url"] = await generate_qr(new_slug)

    update_fields["updated_at"] = datetime.utcnow()

    try:
        updated = await db["digital_cards"].find_one_and_update(
            {"user_id": user_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise SlugAlreadyTaken()

    return updated


# ---------------------------------------------------------------------------
# delete_card — slug freed automatically (unique index released on delete)
# ---------------------------------------------------------------------------

async def delete_card(db: AsyncIOMotorDatabase, user_id: ObjectId) -> None:
    card = await db["digital_cards"].find_one({"user_id": user_id})
    if not card:
        raise CardNotFound()
    await db["digital_cards"].delete_one({"_id": card["_id"]})


# ---------------------------------------------------------------------------
# get_public_card — 404 if not found or is_public=False, atomic view_count++
# ---------------------------------------------------------------------------

async def get_public_card(db: AsyncIOMotorDatabase, slug: str) -> dict:
    card = await db["digital_cards"].find_one_and_update(
        {"slug": slug, "is_public": True},
        {"$inc": {"view_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not card:
        raise CardNotFound()
    return card
