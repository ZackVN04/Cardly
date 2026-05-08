from fastapi import APIRouter

router = APIRouter(prefix="/events", tags=["events"])

# Implementation: Phase 3 — W4 (Khanh)
# GET    /       → 200 OK        → EventListResponse  [Auth]  (query: page, limit)
# POST   /       → 201 Created   → EventResponse      [Auth]
# GET    /{id}   → 200 OK        → EventResponse      [Auth]
# PATCH  /{id}   → 200 OK        → EventResponse      [Auth]
# DELETE /{id}   → 204 No Content                     [Auth]
