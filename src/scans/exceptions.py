from fastapi import HTTPException, status


class ScanNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")


class ScanAlreadyConfirmed(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="Scan already confirmed")


class ScanStillProcessing(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="OCR still processing, try again shortly")


class OCRFailed(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OCR failed to extract data")
