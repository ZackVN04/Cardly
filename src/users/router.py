from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

# Implementation: Phase 3 — W5 (Khanh)
# GET /{userId}  → 200 OK → UserPublic
# GET /          → 200 OK → UserSearchList  (query: q, page, limit)
