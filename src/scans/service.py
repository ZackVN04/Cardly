from fastapi import UploadFile

# Implementation: Phase 3 — W7 (Huy)
# submit_scan(owner_id: str, file: UploadFile, background_tasks: BackgroundTasks) -> ScanResponse
#   Upload image to GCS → create scan doc (status=processing) → enqueue OCR as background task → return 202
# get_scan(scan_id: str, owner_id: str) -> ScanResponse
# list_scans(owner_id: str, page: int, limit: int) -> ScanListResponse
# _process_scan(scan_id: str) -> None  # background: call ocr_client → update doc
