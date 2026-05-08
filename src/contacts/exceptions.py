from fastapi import HTTPException


class ContactNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Contact not found")


class NotContactOwner(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail="Not the contact owner")


class TagAlreadyAdded(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="Tag already added to contact")


class TagNotOnContact(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Tag not found on contact")
