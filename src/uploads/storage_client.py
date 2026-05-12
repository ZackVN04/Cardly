"""
src/uploads/storage_client.py
------------------------------
Async-compatible wrapper cho Google Cloud Storage SDK.

Vấn đề: google-cloud-storage SDK là synchronous hoàn toàn.
Nếu gọi trực tiếp trong async FastAPI handler → block event loop → toàn bộ server bị
treo trong lúc chờ GCS response.

Giải pháp: dùng asyncio.get_event_loop().run_in_executor(None, blocking_fn) để
đẩy blocking call vào ThreadPoolExecutor — event loop tiếp tục xử lý request khác
trong khi thread chờ GCS.
"""

import asyncio
import logging

from fastapi import HTTPException, status
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

from src.core.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — khởi tạo 1 lần duy nhất khi import module
# Tránh tạo mới GCS client cho mỗi request (tốn thời gian auth + connection)
_gcs_client: storage.Client | None = None


# ---------------------------------------------------------------------------
# _get_client — singleton factory, thread-safe với GIL của CPython
# ---------------------------------------------------------------------------

def _get_client() -> storage.Client:
    global _gcs_client

    if _gcs_client is None:
        # Đọc credentials từ GOOGLE_APPLICATION_CREDENTIALS env var
        # storage.Client() tự detect env var này — không hardcode path
        _gcs_client = storage.Client(project=settings.GCS_PROJECT_ID)

    return _gcs_client


# ---------------------------------------------------------------------------
# upload_to_gcs — upload bytes lên GCS và trả về public URL
# ---------------------------------------------------------------------------

async def upload_to_gcs(
    file_bytes: bytes,
    destination_blob_name: str,
    content_type: str,
) -> str:
    """
    Upload file bytes lên GCS bucket.
    Tất cả GCS SDK calls đều chạy trong executor để không block event loop.
    """
    try:
        loop = asyncio.get_running_loop()  # lấy event loop hiện tại của coroutine

        client = _get_client()
        bucket = client.bucket(settings.GCS_BUCKET_NAME)  # không gọi GCS, chỉ tạo reference
        blob = bucket.blob(destination_blob_name)          # tương tự, chỉ là object reference

        # upload_from_string là blocking I/O — đẩy vào thread pool
        # None = dùng default ThreadPoolExecutor của loop
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(file_bytes, content_type=content_type),
        )

        # make_public cũng là HTTP call → executor
        # Làm blob public để frontend có thể load avatar trực tiếp không qua signed URL
        await loop.run_in_executor(None, blob.make_public)

        # blob.public_url là property thuần Python, không gọi GCS → lấy trực tiếp
        return blob.public_url

    except GoogleCloudError as exc:
        # Log chi tiết để debug nhưng KHÔNG expose raw GCS error ra client
        # Raw GCS error có thể chứa bucket name, project ID — thông tin nhạy cảm
        logger.error("GCS upload failed | blob=%s error=%s", destination_blob_name, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File upload failed. Please try again.",
        )


# ---------------------------------------------------------------------------
# delete_from_gcs — xóa blob, silent nếu không tồn tại
# ---------------------------------------------------------------------------

async def delete_from_gcs(blob_name: str) -> None:
    """
    Xóa blob khỏi GCS.
    Không raise nếu blob không tồn tại — idempotent, an toàn khi gọi nhiều lần.
    Dùng cho cleanup khi user đổi avatar.
    """
    try:
        loop = asyncio.get_running_loop()
        client = _get_client()
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)

        # blob.delete() là blocking → executor
        await loop.run_in_executor(None, blob.delete)

    except NotFound:
        # Blob không tồn tại — log warning, không raise
        # Trường hợp: user chưa có avatar cũ, hoặc đã bị xóa trước đó
        logger.warning("GCS delete: blob not found | blob=%s", blob_name)

    except GoogleCloudError as exc:
        # Lỗi GCS khác (network, permission...) — log nhưng không raise
        # delete là fire-and-forget: không để cleanup failure ảnh hưởng đến user
        logger.error("GCS delete failed | blob=%s error=%s", blob_name, exc)


# ---------------------------------------------------------------------------
# get_public_url — reconstruct URL từ blob_name, không cần gọi GCS
# ---------------------------------------------------------------------------

def get_public_url(blob_name: str) -> str:
    """
    Tính public URL từ blob_name mà không cần API call.
    Dùng khi cần URL nhưng đã biết blob_name (ví dụ: sau khi đọc từ DB).
    Format: https://storage.googleapis.com/{bucket}/{blob_name}
    """
    return f"{settings.GCS_BASE_URL}/{settings.GCS_BUCKET_NAME}/{blob_name}"