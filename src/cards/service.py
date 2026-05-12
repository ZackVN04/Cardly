import io
import base64
import uuid

import qrcode
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from src.cards.exceptions import CardAlreadyExists, CardNotFound, SlugConflict
from src.cards.schemas import CardCreate, CardUpdate

_PUBLIC_BASE_URL = "https://cardly.app/c"


def _generate_slug() -> str:
    return uuid.uuid4().hex[:10]


def _generate_qr_code_url(slug: str) -> str:
    url = f"{_PUBLIC_BASE_URL}/{slug}"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


async def get_my_card(db: AsyncIOMotorDatabase, owner_id: ObjectId) -> dict:
    card = await db["digital_cards"].find_one({"owner_id": owner_id})
    if not card:
        raise CardNotFound()
    return card


async def create_card(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    data: CardCreate,
) -> dict:
    if await db["digital_cards"].find_one({"owner_id": owner_id}):
        raise CardAlreadyExists()

    slug = _generate_slug()
    qr_code_url = _generate_qr_code_url(slug)

    doc = {
        "owner_id": owner_id,
        "slug": slug,
        "qr_code_url": qr_code_url,
        "view_count": 0,
        "is_public": data.is_public,
        "title": data.title,
        "bio": data.bio,
        "company": data.company,
        "title_role": data.title_role,
        "email": data.email,
        "phone": data.phone,
        "website": data.website,
        "social_links": data.social_links,
    }

    try:
        result = await db["digital_cards"].insert_one(doc)
    except DuplicateKeyError:
        raise SlugConflict()

    return await db["digital_cards"].find_one({"_id": result.inserted_id})


async def update_card(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    data: CardUpdate,
) -> dict:
    card = await db["digital_cards"].find_one({"owner_id": owner_id})
    if not card:
        raise CardNotFound()

    update_fields = data.model_dump(exclude_none=True)
    if not update_fields:
        return card

    updated = await db["digital_cards"].find_one_and_update(
        {"owner_id": owner_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,
    )
    return updated


async def delete_card(db: AsyncIOMotorDatabase, owner_id: ObjectId) -> None:
    card = await db["digital_cards"].find_one({"owner_id": owner_id})
    if not card:
        raise CardNotFound()
    await db["digital_cards"].delete_one({"owner_id": owner_id})


async def get_public_card(db: AsyncIOMotorDatabase, slug: str) -> dict:
    card = await db["digital_cards"].find_one({"slug": slug})
    if not card or not card.get("is_public", False):
        raise CardNotFound()

    await db["digital_cards"].update_one(
        {"slug": slug},
        {"$inc": {"view_count": 1}},
    )
    card["view_count"] = card.get("view_count", 0) + 1
    return card
