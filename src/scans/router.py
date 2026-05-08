from fastapi import APIRouter

router = APIRouter(prefix="/scans", tags=["scans"])

# Implementation: Phase 3 — W7 (Huy)
# POST /    → 202 Accepted   → ScanResponse   [Auth]  (rate limit: 10/min) multipart/form-data: file
# GET  /    → 200 OK         → ScanListResponse [Auth] (query: page, limit)
# GET  /{id} → 200 OK        → ScanResponse   [Auth]
