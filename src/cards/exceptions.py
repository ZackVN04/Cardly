from fastapi import HTTPException


class CardNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Card not found")


class UserAlreadyHasCard(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="User already has a digital card")


class SlugAlreadyTaken(HTTPException):
    def __init__(self):
        super().__init__(status_code=409, detail="Slug already taken")


class InvalidSlugFormat(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=400,
            detail=(
                "Invalid slug format. "
                "Use 3-30 lowercase letters, digits, or hyphens. "
                "Cannot start with a hyphen."
            ),
        )
