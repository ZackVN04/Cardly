"""
Tạo tài khoản admin trong MongoDB Atlas.
Chạy: python scripts/create_admin.py
"""
import asyncio
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings
from src.core.security import hash_password


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client["Cardly"]

    username = "admin"
    email = "admin@cardly.dev"
    password = "Admin@123"

    existing = await db["users"].find_one({"$or": [{"username": username}, {"email": email}]})
    if existing:
        print(f"User '{username}' already exists — id: {existing['_id']}")
        client.close()
        return

    now = datetime.utcnow()
    doc = {
        "username": username,
        "email": email,
        "hashed_password": hash_password(password),
        "full_name": "Admin",
        "avatar_url": None,
        "bio": None,
        "is_active": True,
        "reset_token": None,
        "reset_token_expiry": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db["users"].insert_one(doc)
    print(f"Created user '{username}' — id: {result.inserted_id}")
    print(f"  username : {username}")
    print(f"  password : {password}")
    client.close()


asyncio.run(main())
