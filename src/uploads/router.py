"""
---------------------
FastAPI router cho Uploads module.
Chỉ có 1 endpoint: POST /uploads/avatar
Sau khi upload GCS thành công → update avatar_url vào users collection.
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, File, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.database import get_database
from src.uploads.schemas import UploadResponse
from src.uploads.service import delete_old_avatar, upload_avatar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])


# ---------------------------------------------------------------------------
# POST /uploads/avatar — upload avatar, thay thế avatar cũ nếu có
# ---------------------------------------------------------------------------

@router.post(
    "/avatar",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload avatar image",
    description=(
        "Upload avatar image. Replaces existing avatar. "
        "Max 5MB. Formats: JPEG, PNG, WebP"
    ),
)
async def upload_avatar_endpoint(
    # File(...) bắt buộc — FastAPI tự trả 422 nếu không gửi file
    # UploadFile stream bytes, không load hết vào memory trước như bytes param
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, WebP, max 5MB)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = str(current_user["_id"])  # str để dùng trong blob_name generation

    # --- Bước 1: Validate + upload GCS ---
    # service.upload_avatar raise 413/415/503 nếu có vấn đề
    response = await upload_avatar(file, owner_id)

    # --- Bước 2: Lấy avatar_url cũ trước khi update ---
    # Cần blob_name cũ để xóa file GCS — URL không đủ để reconstruct blob_name
    # nếu GCS_BASE_URL hoặc bucket thay đổi trong tương lai
    user = await db["users"].find_one(
        {"_id": ObjectId(owner_id)},
        # Chỉ project field cần thiết — không fetch toàn bộ user document
        {"avatar_url": 1, "avatar_blob_name": 1},
    )

    old_blob_name: str | None = user.get("avatar_blob_name") if user else None

    # --- Bước 3: Update avatar_url và avatar_blob_name vào users collection ---
    # Lưu cả blob_name để có thể xóa GCS sau này mà không cần parse URL
    await db["users"].update_one(
        {"_id": ObjectId(owner_id)},
        {"$set": {
            "avatar_url": response.url,
            "avatar_blob_name": response.blob_name,  # lưu để dùng lần upload tiếp theo
        }},
    )

    # --- Bước 4: Xóa avatar cũ khỏi GCS — fire-and-forget ---
    # Làm SAU khi update DB thành công — tránh xóa file cũ rồi DB update fail
    # Nếu delete fail → log warning, không ảnh hưởng response (chỉ waste storage)
    if old_blob_name:
        # Không await với asyncio.create_task vì cần db context còn sống
        # Await trực tiếp nhưng delete_old_avatar không raise — safe
        await delete_old_avatar(old_blob_name)

    return response