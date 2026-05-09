"""
src/activity/service.py
-----------------------
Shared activity logging service for the Cardly project.
This module is the MOST CRITICAL shared utility — every other service calls log_action().
Must be implemented and stable before any other module is built.
"""

import asyncio
import logging
from typing import Literal

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

# Module-level logger — avoids print statements, integrates with app-wide logging config
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# log_action — fire-and-forget insert into contact_activity_logs
# ---------------------------------------------------------------------------

async def log_action(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    action: Literal["created", "updated", "enriched", "tagged", "deleted"],
    source: Literal["scan", "manual", "enrichment", "user_edit"],
    changed_fields: list[str] | None = None,
    previous_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    """
    Insert one activity log document. Never raises — caller must not be blocked
    or broken if logging fails (e.g. network hiccup, DB issue).
    """
    try:
        # Build the document to insert.
        # Use datetime.utcnow() — MongoDB stores UTC, always keep timezone consistent.
        from datetime import datetime

        doc = {
            "contact_id": contact_id,           # ObjectId ref → contacts._id
            "owner_id": owner_id,               # ObjectId ref → users._id
            "action": action,                   # one of the 5 allowed action strings
            "source": source,                   # origin of the change
            "changed_fields": changed_fields or [],   # which fields changed (empty list if none)
            "previous_values": previous_values or {}, # snapshot before change
            "new_values": new_values or {},           # snapshot after change
            "created_at": datetime.utcnow(),    # server-side timestamp, not client
        }

        # Single insert_one — no extra reads, no aggregation.
        # We do NOT await the result object itself; we only await the coroutine
        # to let Motor complete the insert. The InsertOneResult is intentionally
        # discarded — we don't need the inserted _id here.
        await db["contact_activity_logs"].insert_one(doc)

    except Exception as exc:
        # Swallow ALL exceptions — log_action is fire-and-forget.
        # A logging failure must never propagate up and crash the caller's operation.
        logger.error(
            "log_action failed | contact_id=%s action=%s error=%s",
            contact_id, action, exc,
            exc_info=True,  # include full traceback in log output
        )


# ---------------------------------------------------------------------------
# _serialize — convert ObjectId fields to str for router/response layer
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    """
    Convert ObjectId values to str so the dict is JSON-serializable.
    Only touches the known ObjectId fields; leaves everything else untouched.
    Called on every document before returning to the router layer.
    """
    for field in ("_id", "contact_id", "owner_id"):
        if field in doc and isinstance(doc[field], ObjectId):
            doc[field] = str(doc[field])   # ObjectId → plain string
    return doc


# ---------------------------------------------------------------------------
# list_all — paginated activity logs for an owner, with optional filters
# ---------------------------------------------------------------------------

async def list_all(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    action: str | None = None,
    contact_id: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """
    Return (logs, total_count) for a given owner, newest first.
    Supports optional filtering by action and/or contact_id.
    count_documents and find run CONCURRENTLY via asyncio.gather() to minimize latency.
    """
    # --- Build the query filter ---
    query: dict = {"owner_id": owner_id}  # always scope to the authenticated user

    if action:
        # Only add action filter when caller explicitly provides it
        query["action"] = action

    if contact_id:
        # contact_id arrives as a str from the query param — convert to ObjectId
        # for MongoDB comparison. Raises InvalidId if malformed — let it bubble up
        # so the router can return a 422/400.
        query["contact_id"] = ObjectId(contact_id)

    collection = db["contact_activity_logs"]

    # --- Run count + find concurrently ---
    # asyncio.gather() fires both coroutines at the same time instead of
    # sequentially, saving roughly one round-trip latency to MongoDB.
    total_task = collection.count_documents(query)              # coroutine 1: total count
    cursor = (
        collection
        .find(query)                        # coroutine 2: fetch documents
        .sort("created_at", -1)             # -1 = descending (newest first)
        .skip(skip)                         # pagination offset
        .limit(limit)                       # page size cap
    )
    docs_task = cursor.to_list(length=limit)  # materialize cursor into a list

    # Await both simultaneously
    total, docs = await asyncio.gather(total_task, docs_task)

    # Serialize ObjectId fields before handing off to router
    return [_serialize(doc) for doc in docs], total


# ---------------------------------------------------------------------------
# list_by_contact — paginated logs scoped to one specific contact
# ---------------------------------------------------------------------------

async def list_by_contact(
    db: AsyncIOMotorDatabase,
    contact_id: ObjectId,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """
    Return (logs, total_count) for a specific contact, newest first.
    Filters by BOTH contact_id AND owner_id — ownership check prevents
    user A from reading user B's contact logs even if they know the contact_id.
    Uses asyncio.gather() for concurrent count + find.
    """
    # Dual-filter: contact must belong to this owner
    query = {
        "contact_id": contact_id,  # narrows to one contact's logs
        "owner_id": owner_id,      # ownership guard — never skip this
    }

    collection = db["contact_activity_logs"]

    # Same concurrent pattern as list_all — fire count and find together
    total_task = collection.count_documents(query)
    cursor = (
        collection
        .find(query)
        .sort("created_at", -1)    # newest first
        .skip(skip)
        .limit(limit)
    )
    docs_task = cursor.to_list(length=limit)

    total, docs = await asyncio.gather(total_task, docs_task)

    return [_serialize(doc) for doc in docs], total