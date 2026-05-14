import asyncio
import logging
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.activity.service import log_action
from src.enrichment.exceptions import EnrichmentAlreadyRunning, EnrichmentNotFound
from src.enrichment.schemas import EnrichmentUpdate

logger = logging.getLogger(__name__)

_RUNNING_STATUSES = {"pending", "processing"}


async def _get_contact_verified(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> dict:
    contact = await db["contacts"].find_one({"_id": contact_id})
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if contact["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the contact owner")
    return contact


async def trigger_enrichment(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> dict:
    contact = await _get_contact_verified(db, contact_id, owner_id)

    existing = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if existing and existing["status"] in _RUNNING_STATUSES:
        raise EnrichmentAlreadyRunning()

    now = datetime.utcnow()

    if existing:
        await db["enrichment_results"].update_one(
            {"contact_id": contact_id},
            {"$set": {
                "status": "processing",
                "brief": None,
                "keywords": [],
                "highlights": [],
                "linkedin_data": None,
                "facebook_data": None,
                "website_data": None,
                "source": None,
                "enriched_at": now,
            }},
        )
        doc = await db["enrichment_results"].find_one({"contact_id": contact_id})
    else:
        doc = {
            "contact_id": contact_id,
            "status": "processing",
            "brief": None,
            "keywords": [],
            "highlights": [],
            "linkedin_data": None,
            "facebook_data": None,
            "website_data": None,
            "source": None,
            "enriched_at": now,
        }
        result = await db["enrichment_results"].insert_one(doc)
        doc = await db["enrichment_results"].find_one({"_id": result.inserted_id})

    asyncio.create_task(_run_enrichment_async(db, doc["_id"], contact))
    return doc


async def _run_enrichment_async(
    db: AsyncIOMotorDatabase,
    enrichment_id: ObjectId,
    contact: dict,
) -> None:
    from src.enrichment.ai_client import mock_enrich
    from src.core.config import settings

    try:
        if settings.ENVIRONMENT == "test":
            data = mock_enrich(str(contact["_id"]))
        else:
            # W7: replace with real Gemini pipeline
            # from src.enrichment.ai_client import fetch_linkedin_data, call_gemini, parse_enrichment_result
            data = mock_enrich(str(contact["_id"]))

        await db["enrichment_results"].update_one(
            {"_id": enrichment_id},
            {"$set": {**data, "status": "completed", "source": "gemini"}},
        )

        await log_action(
            db=db,
            contact_id=contact["_id"],
            owner_id=contact["owner_id"],
            action="enriched",
            source="enrichment",
            new_values={"brief": data.get("brief"), "keywords": data.get("keywords", [])},
        )

    except Exception as exc:
        logger.error("Enrichment failed for %s: %s", enrichment_id, exc)
        await db["enrichment_results"].update_one(
            {"_id": enrichment_id},
            {"$set": {"status": "failed"}},
        )


async def get_result(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> dict:
    await _get_contact_verified(db, contact_id, owner_id)

    result = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if not result:
        raise EnrichmentNotFound()
    return result


async def update_manual(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    data: EnrichmentUpdate,
) -> dict:
    await _get_contact_verified(db, contact_id, owner_id)

    result = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if not result:
        raise EnrichmentNotFound()

    fields = data.model_dump(exclude_none=True)
    fields["source"] = "manual"

    updated = await db["enrichment_results"].find_one_and_update(
        {"contact_id": contact_id},
        {"$set": fields},
        return_document=ReturnDocument.AFTER,
    )

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="enriched",
        source="manual",
        previous_values={"brief": result.get("brief"), "keywords": result.get("keywords")},
        new_values={k: v for k, v in fields.items() if k != "source"},
    )

    return updated


async def delete_result(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    await _get_contact_verified(db, contact_id, owner_id)

    result = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if not result:
        raise EnrichmentNotFound()

    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="enriched",
        source="user_edit",
        previous_values={"brief": result.get("brief"), "status": result.get("status")},
        new_values={"status": "deleted"},
    )

    await db["enrichment_results"].delete_one({"contact_id": contact_id})


async def list_all(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
    status_filter: str | None = None,
) -> tuple[list[dict], int]:
    contact_ids = await db["contacts"].distinct("_id", {"owner_id": owner_id})

    query: dict = {"contact_id": {"$in": contact_ids}}
    if status_filter:
        query["status"] = status_filter
    total_task = db["enrichment_results"].count_documents(query)
    docs_task = (
        db["enrichment_results"]
        .find(query)
        .sort("enriched_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )

    total, docs = await asyncio.gather(total_task, docs_task)
    return docs, total
