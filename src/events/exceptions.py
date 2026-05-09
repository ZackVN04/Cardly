"""
src/events/exceptions.py
------------------------
Custom exceptions cho Events module.
"""

from fastapi import HTTPException, status


def EventNotFound() -> HTTPException:
    # 404 — event_id không tồn tại hoặc không thuộc owner
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Event not found",
    )


def NotEventOwner() -> HTTPException:
    # 403 — user cố sửa/xóa event của người khác
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to modify this event",
    )
