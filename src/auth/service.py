"""
src/auth/service.py
-------------------
Business logic cho Auth module.
"""

import asyncio
import hashlib
import logging
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.auth.constants import ACCESS_TOKEN_EXPIRE, REFRESH_TOKEN_EXPIRE, RESET_TOKEN_EXPIRE
from src.auth.exceptions import InvalidCredentials, ResetTokenExpired, TokenInvalid
from src.auth.schemas import DeleteAccountReq, PasswordChange, ResetPasswordReq, UserCreate, UserUpdate
from src.auth.utils import create_jwt, create_reset_token, verify_reset_token
from src.core.config import settings
from src.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)


async def get_me(db: AsyncIOMotorDatabase, user_id: ObjectId) -> dict:
    user = await db["users"].find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def register(db: AsyncIOMotorDatabase, data: UserCreate) -> dict:
    existing_username, existing_email = await asyncio.gather(
        db["users"].find_one({"username": data.username}),
        db["users"].find_one({"email": data.email}),
    )
    if existing_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    if existing_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.utcnow()
    doc = {
        "username": data.username,
        "email": data.email,
        "hashed_password": hash_password(data.password),
        "full_name": data.full_name,
        "avatar_url": None,
        "bio": None,
        "is_active": True,
        "reset_token": None,
        "reset_token_expiry": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db["users"].insert_one(doc)
    return await db["users"].find_one({"_id": result.inserted_id})


async def authenticate(db: AsyncIOMotorDatabase, username: str, password: str) -> dict:
    user = await db["users"].find_one({"username": username.lower()})
    if not user or not verify_password(password, user["hashed_password"]):
        raise InvalidCredentials()
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


def create_tokens(user_id: str) -> tuple[str, str]:
    access = create_jwt({"sub": user_id}, ACCESS_TOKEN_EXPIRE, settings.JWT_SECRET)
    refresh = create_jwt({"sub": user_id}, REFRESH_TOKEN_EXPIRE, settings.REFRESH_SECRET)
    return access, refresh


def refresh_token(token: str) -> str:
    from src.auth.utils import verify_jwt
    from src.auth.exceptions import TokenExpired, TokenInvalid as _TokenInvalid
    try:
        payload = verify_jwt(token, settings.REFRESH_SECRET)
    except (TokenExpired, _TokenInvalid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Refresh token expired or invalid")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Refresh token expired or invalid")
    access, _ = create_tokens(user_id)
    return access


async def update_profile(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    data: UserUpdate,
) -> dict:
    update_fields = data.model_dump(exclude_none=True)
    if not update_fields:
        return await db["users"].find_one({"_id": user_id})

    updated = await db["users"].find_one_and_update(
        {"_id": user_id},
        {"$set": {**update_fields, "updated_at": datetime.utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated


async def change_password(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    data: PasswordChange,
) -> None:
    user = await db["users"].find_one({"_id": user_id})
    if not user or not verify_password(data.old_password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong password")

    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {
            "hashed_password": hash_password(data.new_password),
            "updated_at": datetime.utcnow(),
        }},
    )


async def forgot_password(db: AsyncIOMotorDatabase, email: str) -> None:
    user = await db["users"].find_one({"email": email})
    if not user:
        return  # không tiết lộ email có tồn tại hay không

    token = create_reset_token(email, settings.JWT_SECRET)
    # Lưu hash của token thay vì raw — nếu DB bị leak, token không dùng được
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + RESET_TOKEN_EXPIRE

    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"reset_token": token_hash, "reset_token_expiry": expiry}},
    )

    # TODO W8: gửi email thực — hiện tại log raw token để dev test thủ công
    logger.info("PASSWORD RESET TOKEN for %s: %s", email, token)


async def reset_password(db: AsyncIOMotorDatabase, data: ResetPasswordReq) -> None:
    try:
        email = verify_reset_token(data.token, settings.JWT_SECRET)
    except Exception:
        raise ResetTokenExpired()

    # Hash token nhận được rồi so sánh với hash đã lưu — one-time use
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    user = await db["users"].find_one({"email": email, "reset_token": token_hash})
    if not user:
        raise ResetTokenExpired()

    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {
            "hashed_password": hash_password(data.new_password),
            "reset_token": None,
            "reset_token_expiry": None,
            "updated_at": datetime.utcnow(),
        }},
    )


async def delete_account(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    data: DeleteAccountReq,
) -> None:
    user = await db["users"].find_one({"_id": user_id})
    if not user or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong password")

    # Lấy contact_ids để cascade xóa enrichment_results (không có owner_id)
    contact_ids = await db["contacts"].distinct("_id", {"owner_id": user_id})

    await asyncio.gather(
        db["contacts"].delete_many({"owner_id": user_id}),
        db["enrichment_results"].delete_many({"contact_id": {"$in": contact_ids}}),
        db["tags"].delete_many({"owner_id": user_id}),
        db["events"].delete_many({"owner_id": user_id}),
        db["business_card_scans"].delete_many({"owner_id": user_id}),
        db["digital_cards"].delete_many({"user_id": user_id}),
        db["contact_activity_logs"].delete_many({"owner_id": user_id}),
    )

    await db["users"].delete_one({"_id": user_id})
