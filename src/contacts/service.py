import asyncio
import re
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.activity.service import log_action
from src.contacts.exceptions import (
    ContactNotFound,
    NotContactOwner,
    TagAlreadyAdded,
    TagNotOnContact,
)
from src.contacts.schemas import ContactCreate, ContactUpdate


_SORT_MAP: dict[str, tuple[str, int]] = {
    "created_at": ("created_at", -1),
    "updated_at": ("updated_at", -1),
    "full_name": ("full_name", 1),
    "company": ("company", 1),
}


async def create_contact(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    data: ContactCreate,
) -> dict:
    now = datetime.utcnow()

    tag_oids: list[ObjectId] = []
    for tid in data.tag_ids:
        try:
            tag_oids.append(ObjectId(tid))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid tag ID: {tid}",
            )

    event_oid = ObjectId(data.event_id) if data.event_id else None
    scan_oid = ObjectId(data.scan_id) if data.scan_id else None

    doc = {
        "owner_id": owner_id,
        "scan_id": scan_oid,
        "event_id": event_oid,
        "tag_ids": tag_oids,
        "full_name": data.full_name,
        "position": data.position,
        "company": data.company,
        "phone": data.phone,
        "email": data.email,
        "website": data.website,
        "linkedin_url": data.linkedin_url,
        "facebook_url": data.facebook_url,
        "address": data.address,
        "notes": data.notes,
        "created_at": now,
        "updated_at": now,
    }

    result = await db["contacts"].insert_one(doc)
    inserted = await db["contacts"].find_one({"_id": result.inserted_id})

    await log_action(
        db=db,
        contact_id=result.inserted_id,
        owner_id=owner_id,
        action="created",
        source="manual",
        new_values={"full_name": data.full_name, "company": data.company},
    )

    return inserted


async def list_contacts(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
    q: str | None = None,
    tag_id: str | None = None,
    event_id: str | None = None,
    sort_by: str = "created_at",
) -> tuple[list[dict], int]:
    query: dict = {"owner_id": owner_id}

    if q:
        pattern = re.compile(re.escape(q), re.IGNORECASE)
        query["$or"] = [
            {"full_name": {"$regex": pattern}},
            {"company": {"$regex": pattern}},
        ]

    if tag_id:
        try:
            query["tag_ids"] = ObjectId(tag_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid tag ID format",
            )

    if event_id:
        try:
            query["event_id"] = ObjectId(event_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid event ID format",
            )

    sort_field, sort_dir = _SORT_MAP.get(sort_by, ("created_at", -1))

    collection = db["contacts"]
    total_task = collection.count_documents(query)
    docs_task = (
        collection
        .find(query)
        .sort(sort_field, sort_dir)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )

    total, docs = await asyncio.gather(total_task, docs_task)
    return docs, total


async def get_contact(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> dict:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise ContactNotFound()
    if contact["owner_id"] != owner_id:
        raise NotContactOwner()
    return contact


async def update_contact(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    data: ContactUpdate,
) -> dict:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise ContactNotFound()
    if contact["owner_id"] != owner_id:
        raise NotContactOwner()

    # exclude_unset: bỏ field không gửi; giữ field được gửi kể cả null (để unlink event_id)
    update_fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None or k == "event_id"}
    if not update_fields:
        return contact

    # Chuyển event_id string → ObjectId (hoặc giữ None để unlink)
    if "event_id" in update_fields:
        raw = update_fields["event_id"]
        if raw is not None:
            try:
                update_fields["event_id"] = ObjectId(raw)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid event_id format",
                )

    previous_values = {k: contact.get(k) for k in update_fields}

    updated = await db["contacts"].find_one_and_update(
        {"_id": contact_id},
        {"$set": {**update_fields, "updated_at": datetime.utcnow()}},
        return_document=ReturnDocument.AFTER,
    )

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="updated",
        source="user_edit",
        changed_fields=list(update_fields.keys()),
        previous_values=previous_values,
        new_values=update_fields,
    )

    return updated


async def delete_contact(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise ContactNotFound()
    if contact["owner_id"] != owner_id:
        raise NotContactOwner()

    await asyncio.gather(
        db["contacts"].delete_one({"_id": contact_id}),
        db["enrichment_results"].delete_one({"contact_id": contact_id}),
    )

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="deleted",
        source="user_edit",
        previous_values={"full_name": contact["full_name"], "company": contact.get("company")},
    )


async def add_tag(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    tag_id: ObjectId,
) -> dict:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise ContactNotFound()
    if contact["owner_id"] != owner_id:
        raise NotContactOwner()

    tag = await db["tags"].find_one({"_id": tag_id, "owner_id": owner_id})
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if tag_id in contact.get("tag_ids", []):
        raise TagAlreadyAdded()

    updated = await db["contacts"].find_one_and_update(
        {"_id": contact_id},
        {
            "$addToSet": {"tag_ids": tag_id},
            "$set": {"updated_at": datetime.utcnow()},
        },
        return_document=ReturnDocument.AFTER,
    )

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="tagged",
        source="user_edit",
        changed_fields=["tag_ids"],
        new_values={"tag_id": str(tag_id), "tag_name": tag["name"]},
    )

    return updated


async def remove_tag(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    tag_id: ObjectId,
) -> dict:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise ContactNotFound()
    if contact["owner_id"] != owner_id:
        raise NotContactOwner()

    if tag_id not in contact.get("tag_ids", []):
        raise TagNotOnContact()

    updated = await db["contacts"].find_one_and_update(
        {"_id": contact_id},
        {
            "$pull": {"tag_ids": tag_id},
            "$set": {"updated_at": datetime.utcnow()},
        },
        return_document=ReturnDocument.AFTER,
    )

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="tagged",
        source="user_edit",
        changed_fields=["tag_ids"],
        previous_values={"tag_ids": [str(t) for t in contact.get("tag_ids", [])]},
        new_values={"tag_ids": [str(t) for t in updated.get("tag_ids", [])]},
    )

    return updated
