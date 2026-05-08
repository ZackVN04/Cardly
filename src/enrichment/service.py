# Implementation: Phase 3 — W7 (Huy)
# submit_enrichment(contact_id: str, owner_id: str, background_tasks: BackgroundTasks) -> EnrichmentResponse
#   Create enrichment doc (status=processing) → enqueue AI enrichment as background task → return 202
# get_enrichment(enrichment_id: str, owner_id: str) -> EnrichmentResponse
# list_enrichments(owner_id: str, page: int, limit: int) -> EnrichmentListResponse
# _process_enrichment(enrichment_id: str) -> None  # background: call ai_client → update doc + contact
