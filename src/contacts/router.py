from fastapi import APIRouter

router = APIRouter(prefix="/contacts", tags=["contacts"])

# Implementation: Phase 3 — W4 (Huy)
# GET /  · POST /  · GET /{id}  · PATCH /{id}  · DELETE /{id}
# POST /{id}/tags  · DELETE /{id}/tags/{tagId}
