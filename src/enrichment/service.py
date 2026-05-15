import asyncio
import logging
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.activity.service import log_action
from src.core.config import settings
from src.enrichment.ai_client import (
    call_gemini,
    fetch_facebook_data,
    fetch_linkedin_data,
    fetch_website_data,
    mock_enrich,
)
from src.enrichment.exceptions import EnrichmentAlreadyRunning, EnrichmentNotFound
from src.enrichment.schemas import EnrichmentUpdate

logger = logging.getLogger(__name__)

_RUNNING_STATUSES = {"pending", "processing"}

# All fields that constitute an enrichment result — used for snapshots in activity logs
_ENRICHMENT_FIELDS = [
    "brief",
    "keywords",
    "highlights",
    "linkedin_data",
    "facebook_data",
    "website_data",
]

_EMPTY_ENRICHMENT: dict = {
    "brief": None,
    "keywords": [],
    "highlights": [],
    "linkedin_data": None,
    "facebook_data": None,
    "website_data": None,
}


def _snapshot(doc: dict) -> dict:
    """Extract enrichment fields from a DB document for activity log snapshots."""
    return {f: doc.get(f) for f in _ENRICHMENT_FIELDS}


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
        # Archive previous completed result before wiping — per API spec re-run flow
        if existing.get("status") == "completed":
            await log_action(
                db=db,
                contact_id=contact_id,
                owner_id=owner_id,
                action="enriched",
                source="enrichment",
                changed_fields=_ENRICHMENT_FIELDS,
                previous_values=_snapshot(existing),
                new_values=_EMPTY_ENRICHMENT.copy(),
            )

        await db["enrichment_results"].update_one(
            {"contact_id": contact_id},
            {
                "$set": {
                    "status": "processing",
                    "source": None,
                    "enriched_at": now,
                    **_EMPTY_ENRICHMENT,
                }
            },
        )
        doc = await db["enrichment_results"].find_one({"contact_id": contact_id})
    else:
        doc = {
            "contact_id": contact_id,
            "status": "processing",
            "source": None,
            "enriched_at": now,
            **_EMPTY_ENRICHMENT,
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
    try:
        if settings.ENVIRONMENT == "test":
            data = mock_enrich(str(contact["_id"]))
        else:
            linkedin_data, website_data, facebook_data = await asyncio.gather(
                fetch_linkedin_data(contact.get("linkedin_url") or ""),
                fetch_website_data(contact.get("website") or ""),
                fetch_facebook_data(contact.get("facebook_url") or ""),
            )
            social_data = {
                "linkedin_data": linkedin_data,
                "website_data": website_data,
                "facebook_data": facebook_data,
            }
            gemini_result = await call_gemini(contact, social_data)
            data = {
                **gemini_result,
                "linkedin_data": linkedin_data,
                "facebook_data": facebook_data,
                "website_data": website_data,
            }

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
            changed_fields=_ENRICHMENT_FIELDS,
            previous_values=_EMPTY_ENRICHMENT.copy(),
            new_values={f: data.get(f) for f in _ENRICHMENT_FIELDS},
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

    existing = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if not existing:
        raise EnrichmentNotFound()

    fields = data.model_dump(exclude_none=True)
    changed = list(fields.keys())
    previous_values = {k: existing.get(k) for k in changed}

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
        changed_fields=changed,
        previous_values=previous_values,
        new_values={k: fields[k] for k in changed},
    )

    return updated


async def delete_result(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    await _get_contact_verified(db, contact_id, owner_id)

    existing = await db["enrichment_results"].find_one({"contact_id": contact_id})
    if not existing:
        raise EnrichmentNotFound()

    # Log full snapshot before deletion — new_values = all null/empty per API spec
    await log_action(
        db=db,
        contact_id=contact_id,
        owner_id=owner_id,
        action="enriched",
        source="user_edit",
        changed_fields=_ENRICHMENT_FIELDS,
        previous_values=_snapshot(existing),
        new_values=_EMPTY_ENRICHMENT.copy(),
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
