from fastapi import APIRouter

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Implementation: Phase 3 — W6 (Huy)
# POST /avatar → 200 OK → UploadResponse  [Auth]  multipart/form-data: file
