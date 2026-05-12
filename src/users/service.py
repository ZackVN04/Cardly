import asyncio

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.users.exceptions import UserNotFound


async def get_public_profile(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        raise UserNotFound()

    user = await db["users"].find_one({"_id": oid})
    if not user:
        raise UserNotFound()
    return user


async def search_users(
    db: AsyncIOMotorDatabase,
    q: str,
    skip: int,
    limit: int,
) -> tuple[list[dict], int]:
    pattern = {"$regex": q, "$options": "i"}
    query = {"$or": [{"username": pattern}, {"full_name": pattern}]}

    total, items = await asyncio.gather(
        db["users"].count_documents(query),
        db["users"].find(query).skip(skip).limit(limit).to_list(length=limit),
    )

    return items, total
