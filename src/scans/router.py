from fastapi import APIRouter

router = APIRouter(prefix="/scans", tags=["scans"])

# Implementation: Phase 3 — W6 (Huy)
# GET /  · POST / (upload+OCR)  · GET /{id}  · PATCH /{id}
# POST /{id}/confirm  · DELETE /{id}
