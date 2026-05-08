from fastapi import APIRouter

router = APIRouter(prefix="/cards", tags=["cards"])

# Implementation: Phase 4 — W8 (Khanh)
# GET /me  · POST /me  · PATCH /me  · DELETE /me
# GET /public/{slug}  [no auth]
