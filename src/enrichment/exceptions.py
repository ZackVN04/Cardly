from fastapi import HTTPException, status


class EnrichmentNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Enrichment result not found")


class EnrichmentAlreadyRunning(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="Enrichment already running for this contact")
