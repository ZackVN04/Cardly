"""

----------------------
Business logic cho uploads module.
Validate → generate blob name → upload GCS.

Thứ tự validate quan trọng: MIME → size → extension
- MIME check trước size vì không cần đọc file bytes (dùng content_type header)
- Size check sau khi đã đọc bytes (không tránh được)
- Extension check cuối — chỉ là guard thêm, hiếm khi fail nếu MIME đúng
"""

import pathlib
import uuid
from datetime import datetime

from fastapi import HTTPException, UploadFile, status

from src.uploads.constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    AVATAR_FOLDER,
    MAX_FILE_SIZE,
)
from src.uploads.schemas import UploadResponse
from src.uploads.storage_client import delete_from_gcs, upload_to_gcs


# ---------------------------------------------------------------------------
# upload_avatar — validate + upload file lên GCS
# ---------------------------------------------------------------------------

async def upload_avatar(file: UploadFile, owner_id: str) -> UploadResponse:
    """
    Validate file và upload lên GCS.
    Fail fast: check rẻ nhất trước (MIME từ header), check đắt nhất sau (đọc bytes).
    """

    # --- Bước 1: Validate MIME type từ Content-Type header ---
    # Kiểm tra trước khi đọc bytes — không tốn I/O nếu sai ngay từ đầu
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Allowed: JPEG, PNG, WebP",
        )

    # --- Bước 2: Đọc toàn bộ file vào memory ---
    # Cardly chỉ xử lý avatar ≤5MB nên in-memory an toàn
    # Không ghi ra disk → tránh race condition và cleanup phức tạp
    content = await file.read()

    # --- Bước 3: Validate kích thước sau khi đọc ---
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File too large. Maximum size is 5MB",
        )

    # --- Bước 4: Validate extension từ filename ---
    # pathlib.Path tự xử lý edge case: "photo", "photo.", "dir/photo.jpg"
    # Không dùng split('.') vì không handle được "photo.tar.gz" hay filename không có ext
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid file extension. Allowed: .jpg, .jpeg, .png, .webp",
        )

    # --- Bước 5: Generate blob name duy nhất ---
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")  # ví dụ: 20260510143022
    unique_id = uuid.uuid4().hex[:8]                          # 8 ký tự hex ngẫu nhiên

    # Format: avatars/{owner_id}_{timestamp}_{unique_id}.ext
    # - owner_id: biết file thuộc về ai mà không cần query DB
    # - timestamp: sort theo thời gian trong GCS console
    # - unique_id: tránh collision nếu cùng owner upload cùng giây
    # - Không dùng filename gốc: tránh path traversal attack (ví dụ: "../../../etc/passwd")
    blob_name = f"{AVATAR_FOLDER}/{owner_id}_{timestamp}_{unique_id}{ext}"

    # --- Bước 6: Upload lên GCS ---
    # upload_to_gcs tự wrap blocking SDK call vào executor
    # Raise 503 nếu GCS fail — propagate lên router
    public_url = await upload_to_gcs(content, blob_name, file.content_type)

    # --- Bước 7: Trả về response ---
    return UploadResponse(url=public_url, blob_name=blob_name)


# ---------------------------------------------------------------------------
# delete_old_avatar — xóa avatar cũ khỏi GCS khi user upload avatar mới
# ---------------------------------------------------------------------------

async def delete_old_avatar(blob_name: str) -> None:
    """
    Fire-and-forget cleanup — xóa file cũ để tiết kiệm GCS storage.
    Không raise dù GCS fail — không để cleanup ảnh hưởng đến UX của user.
    delete_from_gcs() đã handle silent error internally.
    """
    await delete_from_gcs(blob_name)