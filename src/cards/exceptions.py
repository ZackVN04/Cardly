from fastapi import HTTPException, status


class CardNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Digital card not found")


class SlugAlreadyTaken(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="Slug is already taken")


class UserAlreadyHasCard(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="User already has a digital card")


class InvalidSlugFormat(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slug format")
