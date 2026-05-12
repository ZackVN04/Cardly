from bson import ObjectId
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.contacts.exceptions import ContactNotFound, NotContactOwner
from src.database import get_database


async def get_contact_or_404(
    contact_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    try:
        oid = ObjectId(contact_id)
    except Exception:
        raise ContactNotFound()
    contact = await db["contacts"].find_one({"_id": oid})
    if not contact:
        raise ContactNotFound()
    return contact


def verify_contact_owner(contact: dict, current_user: dict) -> None:
    if contact["owner_id"] != ObjectId(current_user["_id"]):
        raise NotContactOwner()
