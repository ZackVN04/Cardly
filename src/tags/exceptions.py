from fastapi import HTTPException


class TagNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Tag not found")


class TagNameConflict(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="Tag name already exists")
