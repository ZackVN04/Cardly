from fastapi import HTTPException


class ScanNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Scan not found")


class ScanProcessingFailed(HTTPException):
    def __init__(self):
        super().__init__(status_code=422, detail="Scan processing failed")
