from fastapi import HTTPException


class EventNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Event not found")


class NotEventOwner(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail="Not the event owner")
