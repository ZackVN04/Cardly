from fastapi import APIRouter

router = APIRouter(prefix="/activity", tags=["activity"])

# Implementation: Phase 3 — W6 (Huy)
# GET / → 200 OK → ActivityLogList  [Auth]  (query: page, limit)
