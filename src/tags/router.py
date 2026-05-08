from fastapi import APIRouter

router = APIRouter(prefix="/tags", tags=["tags"])

# Implementation: Phase 3 — W4 (Khanh)
# GET    /       → 200 OK        → list[TagResponse]  [Auth]
# POST   /       → 201 Created   → TagResponse        [Auth]
# PATCH  /{id}   → 200 OK        → TagResponse        [Auth]
# DELETE /{id}   → 204 No Content                     [Auth]
