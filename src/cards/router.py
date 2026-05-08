from fastapi import APIRouter

router = APIRouter(prefix="/cards", tags=["cards"])
public_router = APIRouter(prefix="/public", tags=["public"])

# Implementation: Phase 3 — W6 (Huy)
#
# router (requires Auth):
# GET    /me    → 200 OK        → CardResponse  [Auth]
# POST   /me    → 201 Created   → CardResponse  [Auth]
# PATCH  /me    → 200 OK        → CardResponse  [Auth]
# DELETE /me    → 204 No Content                [Auth]
#
# public_router (no auth):
# GET    /{slug} → 200 OK → CardResponse  (increments view_count; 404 if is_public=False)
