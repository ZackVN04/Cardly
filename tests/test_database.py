"""
W3 integration tests — database.py
Tests cover: collection name mapping, get_database guard, lifespan connect+index.
Requires a live MongoDB connection (reads from .env).
"""
import pytest

import src.database as db_module
from src.database import (
    get_activity_logs_collection,
    get_cards_collection,
    get_contacts_collection,
    get_database,
    get_enrichments_collection,
    get_events_collection,
    get_scans_collection,
    get_tags_collection,
    get_users_collection,
)


# ---------------------------------------------------------------------------
# Guard: get_database() before connect raises RuntimeError
# ---------------------------------------------------------------------------


def test_get_database_raises_before_connect(monkeypatch):
    monkeypatch.setattr(db_module, "_db", None)
    with pytest.raises(RuntimeError, match="Database not connected"):
        get_database()


# ---------------------------------------------------------------------------
# Collection name mapping (requires live DB via async_client lifespan)
# ---------------------------------------------------------------------------


async def test_users_collection_name(async_client):
    assert get_users_collection().name == "users"


async def test_contacts_collection_name(async_client):
    assert get_contacts_collection().name == "contacts"


async def test_scans_collection_name(async_client):
    assert get_scans_collection().name == "business_card_scans"


async def test_enrichments_collection_name(async_client):
    assert get_enrichments_collection().name == "enrichment_results"


async def test_tags_collection_name(async_client):
    assert get_tags_collection().name == "tags"


async def test_events_collection_name(async_client):
    assert get_events_collection().name == "events"


async def test_cards_collection_name(async_client):
    assert get_cards_collection().name == "digital_cards"


async def test_activity_logs_collection_name(async_client):
    assert get_activity_logs_collection().name == "contact_activity_logs"


# ---------------------------------------------------------------------------
# get_database() returns correct DB after connect (via async_client fixture)
# ---------------------------------------------------------------------------


async def test_get_database_returns_instance(async_client):
    db = get_database()
    assert db is not None


async def test_get_database_has_string_name(async_client):
    db = get_database()
    assert isinstance(db.name, str)
    assert len(db.name) > 0


# ---------------------------------------------------------------------------
# Indexes created by create_indexes() (integration — hits Atlas)
# ---------------------------------------------------------------------------


async def test_users_username_index_unique(async_client):
    db = get_database()
    indexes = await db["users"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("username", 1)]), None)
    assert idx is not None, "username index missing"
    assert idx.get("unique") is True


async def test_users_email_index_unique(async_client):
    db = get_database()
    indexes = await db["users"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("email", 1)]), None)
    assert idx is not None, "email index missing"
    assert idx.get("unique") is True


async def test_contacts_owner_id_index_exists(async_client):
    db = get_database()
    indexes = await db["contacts"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("owner_id", 1)]), None)
    assert idx is not None, "contacts owner_id index missing"


async def test_contacts_event_id_index_exists(async_client):
    db = get_database()
    indexes = await db["contacts"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("event_id", 1)]), None)
    assert idx is not None, "contacts event_id index missing"


async def test_contacts_tag_ids_index_exists(async_client):
    db = get_database()
    indexes = await db["contacts"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("tag_ids", 1)]), None)
    assert idx is not None, "contacts tag_ids index missing"


async def test_contacts_scan_id_index_exists(async_client):
    db = get_database()
    indexes = await db["contacts"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("scan_id", 1)]), None)
    assert idx is not None, "contacts scan_id index missing"


async def test_contacts_text_index_exists(async_client):
    db = get_database()
    indexes = await db["contacts"].index_information()
    idx = next(
        (v for v in indexes.values() if any(t == "text" for _, t in v["key"])), None
    )
    assert idx is not None, "contacts text index missing"


async def test_scans_status_index_exists(async_client):
    db = get_database()
    indexes = await db["business_card_scans"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("status", 1)]), None)
    assert idx is not None, "business_card_scans status index missing"


async def test_enrichment_results_contact_id_unique(async_client):
    db = get_database()
    indexes = await db["enrichment_results"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("contact_id", 1)]), None)
    assert idx is not None, "enrichment_results contact_id index missing"
    assert idx.get("unique") is True, "enrichment_results contact_id must be unique"


async def test_digital_cards_slug_unique(async_client):
    db = get_database()
    indexes = await db["digital_cards"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("slug", 1)]), None)
    assert idx is not None, "digital_cards slug index missing"
    assert idx.get("unique") is True


async def test_digital_cards_user_id_index_exists(async_client):
    db = get_database()
    indexes = await db["digital_cards"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("user_id", 1)]), None)
    assert idx is not None, "digital_cards user_id index missing"


async def test_activity_logs_contact_id_index_exists(async_client):
    db = get_database()
    indexes = await db["contact_activity_logs"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("contact_id", 1)]), None)
    assert idx is not None, "contact_activity_logs contact_id index missing"


async def test_activity_logs_owner_id_index_exists(async_client):
    db = get_database()
    indexes = await db["contact_activity_logs"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("owner_id", 1)]), None)
    assert idx is not None, "contact_activity_logs owner_id index missing"


async def test_activity_logs_created_at_index_exists(async_client):
    db = get_database()
    indexes = await db["contact_activity_logs"].index_information()
    idx = next((v for v in indexes.values() if v["key"] == [("created_at", 1)]), None)
    assert idx is not None, "contact_activity_logs created_at index missing"
