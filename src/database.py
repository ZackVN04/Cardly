from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from src.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client.get_default_database()
    await create_indexes()


async def disconnect_db() -> None:
    if _client:
        _client.close()


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised — call connect_db() first")
    return _db


def get_users_collection() -> AsyncIOMotorCollection:
    return get_database()["users"]


def get_contacts_collection() -> AsyncIOMotorCollection:
    return get_database()["contacts"]


def get_scans_collection() -> AsyncIOMotorCollection:
    return get_database()["business_card_scans"]


def get_enrichments_collection() -> AsyncIOMotorCollection:
    return get_database()["enrichment_results"]


def get_tags_collection() -> AsyncIOMotorCollection:
    return get_database()["tags"]


def get_events_collection() -> AsyncIOMotorCollection:
    return get_database()["events"]


def get_cards_collection() -> AsyncIOMotorCollection:
    return get_database()["digital_cards"]


def get_activity_logs_collection() -> AsyncIOMotorCollection:
    return get_database()["contact_activity_logs"]


async def create_indexes() -> None:
    db = get_database()

    await db["users"].create_index("username", unique=True)
    await db["users"].create_index("email", unique=True)
    await db["users"].create_index("reset_token")

    await db["digital_cards"].create_index("slug", unique=True)
    await db["digital_cards"].create_index("user_id")

    await db["contacts"].create_index("owner_id")
    await db["contacts"].create_index("event_id")
    await db["contacts"].create_index("tag_ids")
    await db["contacts"].create_index("scan_id")
    await db["contacts"].create_index([("full_name", "text"), ("company", "text")])

    await db["business_card_scans"].create_index("owner_id")
    await db["business_card_scans"].create_index("status")

    await db["enrichment_results"].create_index("contact_id", unique=True)

    await db["tags"].create_index("owner_id")

    await db["events"].create_index("owner_id")

    await db["contact_activity_logs"].create_index("contact_id")
    await db["contact_activity_logs"].create_index("owner_id")
    await db["contact_activity_logs"].create_index("created_at")
