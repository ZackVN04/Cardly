from fastapi import HTTPException


class EnrichmentNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Enrichment result not found")


class EnrichmentAlreadyRunning(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="Enrichment is already running for this contact")


class EnrichmentFailed(HTTPException):
    def __init__(self):
        super().__init__(status_code=422, detail="AI enrichment processing failed")
