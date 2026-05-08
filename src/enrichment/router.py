from fastapi import APIRouter

router = APIRouter(prefix="/enrichment", tags=["enrichment"])

# Implementation: Phase 3 — W7 (Huy)
# POST /contacts/{contact_id}/enrich → 202 Accepted → EnrichmentResponse  [Auth]  (rate limit: 5/min)
# GET  /contacts/{contact_id}/enrich → 200 OK       → EnrichmentListResponse [Auth]
# GET  /{id}                         → 200 OK        → EnrichmentResponse  [Auth]
