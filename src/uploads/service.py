from fastapi import UploadFile

# Implementation: Phase 3 — W6 (Huy)
# upload_avatar(user_id: str, file: UploadFile) -> str
#   Validate content_type in ALLOWED_IMAGE_TYPES and size <= MAX_FILE_SIZE
#   Upload to GCS at path: avatars/{user_id}/{uuid}.{ext}
#   Return public URL string
