from fastapi import HTTPException


def UserNotFound():
    return HTTPException(status_code=404, detail="User not found")
