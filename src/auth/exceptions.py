from fastapi import HTTPException


class InvalidCredentials(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Invalid credentials")


class TokenExpired(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token has expired")


class TokenInvalid(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token is invalid")


class ResetTokenExpired(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="Reset token has expired")
