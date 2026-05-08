from fastapi import HTTPException


class EnrichmentNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Enrichment not found")


class EnrichmentFailed(HTTPException):
    def __init__(self):
        super().__init__(status_code=422, detail="AI enrichment failed")
