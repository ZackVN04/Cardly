from fastapi import APIRouter

router = APIRouter(prefix="/contacts", tags=["contacts"])

# Implementation: Phase 3 — W6 (Khanh)
# GET    /           → 200 OK  → ContactListResponse  [Auth]  (query: page, limit, q, tag_id, event_id, sort_by)
# POST   /           → 201 Created → ContactResponse   [Auth]
# GET    /{id}       → 200 OK  → ContactResponse       [Auth]
# PATCH  /{id}       → 200 OK  → ContactResponse       [Auth]
# DELETE /{id}       → 204 No Content                  [Auth]
# POST   /{id}/tags  → 200 OK  → ContactResponse       [Auth]  (body: {tag_id})
# DELETE /{id}/tags/{tag_id} → 204 No Content          [Auth]
