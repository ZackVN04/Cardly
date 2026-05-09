from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from src.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    # tlsAllowInvalidCertificates=True giải quyết lỗi TLSV1_ALERT_INTERNAL_ERROR
    # thường gặp trên Windows khi kết nối MongoDB Atlas qua môi trường dev
    _client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        tlsAllowInvalidCertificates=True,
    )
    _db = _client[settings.MONGODB_DB_NAME]


async def disconnect_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db


def get_users_collection() -> AsyncIOMotorCollection:
    return get_database()["users"]


def get_contacts_collection() -> AsyncIOMotorCollection:
    return get_database()["contacts"]


def get_scans_collection() -> AsyncIOMotorCollection:
    return get_database()["scans"]


def get_enrichments_collection() -> AsyncIOMotorCollection:
    return get_database()["enrichments"]


def get_tags_collection() -> AsyncIOMotorCollection:
    return get_database()["tags"]


def get_events_collection() -> AsyncIOMotorCollection:
    return get_database()["events"]


def get_cards_collection() -> AsyncIOMotorCollection:
    return get_database()["cards"]


def get_activity_logs_collection() -> AsyncIOMotorCollection:
    return get_database()["activity_logs"]


async def create_indexes() -> None:
    db = get_database()

    # users
    await db["users"].create_index("username", unique=True)
    await db["users"].create_index("email", unique=True)
    await db["users"].create_index("reset_token", sparse=True)

    # contacts
    await db["contacts"].create_index("owner_id")
    await db["contacts"].create_index([("full_name", "text"), ("company", "text")])

    # tags
    await db["tags"].create_index("owner_id")

    # events
    await db["events"].create_index("owner_id")

    # scans
    await db["scans"].create_index("owner_id")

    # enrichments
    await db["enrichments"].create_index("owner_id")
    await db["enrichments"].create_index("contact_id")

    # cards
    await db["cards"].create_index("slug", unique=True)
    await db["cards"].create_index("owner_id", unique=True)

    # activity_logs
    await db["activity_logs"].create_index("user_id")
    await db["activity_logs"].create_index("created_at")
