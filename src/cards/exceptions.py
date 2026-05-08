from fastapi import HTTPException


class CardNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Card not found")


class CardAlreadyExists(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="User already has a digital card")


class SlugConflict(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="Slug already in use")
