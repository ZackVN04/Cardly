# from fastapi import HTTPException


# class TagNotFound(HTTPException):
#     def __init__(self):
#         super().__init__(status_code=404, detail="Tag not found")


# class TagNameConflict(HTTPException):
#     def __init__(self):
#         super().__init__(status_code=409, detail="Tag name already exists")


"""
src/tags/exceptions.py
----------------------
Custom exceptions cho Tags module.
Dùng pattern raise trực tiếp HTTPException thay vì subclass
để giữ đơn giản và nhất quán với FastAPI convention.
"""

from fastapi import HTTPException, status


def TagNotFound() -> HTTPException:
    # 404 — tag_id không tồn tại trong collection
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tag not found",
    )


def DuplicateTagName() -> HTTPException:
    # 409 — owner đã có tag cùng tên (unique per owner, không phải global)
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Tag name already exists",
    )


def NotTagOwner() -> HTTPException:
    # 403 — user cố sửa/xóa tag của người khác
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to modify this tag",
    )