from fastapi import HTTPException


class ScanNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Scan not found")


class NotScanOwner(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail="Not the scan owner")


class ScanAlreadyConfirmed(HTTPException):
    """409 — dùng khi gọi POST /confirm lần 2 trên cùng một scan."""
    def __init__(self):
        super().__init__(status_code=409, detail="Scan already confirmed")


class ScanNotCompleted(HTTPException):
    """400 — POST /confirm yêu cầu status='completed'; PATCH yêu cầu chưa confirmed."""
    def __init__(self):
        super().__init__(status_code=400, detail="Scan must be in 'completed' status to confirm")


class CannotEditConfirmedScan(HTTPException):
    """400 — PATCH bị chặn khi scan đã confirmed."""
    def __init__(self):
        super().__init__(status_code=400, detail="Cannot edit a scan that is already confirmed")


class ScanStillProcessing(HTTPException):
    """408 — GET /{id} trả về khi scan vẫn đang xử lý sau 30 giây."""
    def __init__(self):
        super().__init__(status_code=408, detail="Scan is still processing, please retry")


class OCRFailed(HTTPException):
    """422 — OCR pipeline thất bại, không extract được data."""
    def __init__(self):
        super().__init__(status_code=422, detail="OCR processing failed")


class UnsupportedFileType(HTTPException):
    """415 — POST /: file không phải JPEG/PNG/WEBP."""
    def __init__(self):
        super().__init__(status_code=415, detail="Unsupported file type. Allowed: JPEG, PNG, WEBP")


class FileTooLarge(HTTPException):
    """413 — POST /: file vượt quá 5MB."""
    def __init__(self):
        super().__init__(status_code=413, detail="File too large. Maximum size is 5MB")
