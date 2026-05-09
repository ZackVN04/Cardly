# from fastapi import APIRouter

# router = APIRouter(prefix="/tags", tags=["tags"])

# Implementation: Phase 3 — W4 (Khanh)
# GET    /       → 200 OK        → list[TagResponse]  [Auth]
# POST   /       → 201 Created   → TagResponse        [Auth]
# PATCH  /{id}   → 200 OK        → TagResponse        [Auth]
# DELETE /{id}   → 204 No Content                     [Auth]



"""
src/tags/router.py
------------------
FastAPI router cho Tags module.
Tất cả route đều yêu cầu xác thực — current_user inject qua Depends.
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.database import get_database               # dependency trả về db instance
from src.core.pagination import PaginatedResponse   # generic wrapper {items, total, skip, limit}
from src.auth.dependencies import get_current_user  # dependency trả về user dict từ JWT
from src.tags import service
from src.tags.schemas import TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


# ---------------------------------------------------------------------------
# Helper — validate ObjectId từ path param
# ---------------------------------------------------------------------------

def parse_object_id(raw: str) -> ObjectId:
    """
    Convert string path param → ObjectId.
    Raise 422 ngay tại router nếu format sai, không để lỗi rơi xuống service.
    """
    try:
        return ObjectId(raw)
    except Exception:
        # ObjectId() raise InvalidId (subclass của Exception) nếu format sai
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid tag ID format",
        )


# ---------------------------------------------------------------------------
# GET / — lấy danh sách tags của user hiện tại
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[TagResponse])
async def list_tags(
    skip: int = Query(default=0, ge=0),               # offset, không âm
    limit: int = Query(default=20, ge=1, le=100),     # max 100 để tránh abuse
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])  # lấy ObjectId từ user đã auth

    tags, total = await service.list_tags(db, owner_id, skip=skip, limit=limit)

    # Dùng .build() để tự tính pages — PaginatedResponse yêu cầu pages (không có default)
    return PaginatedResponse.build(
        items=[TagResponse.model_validate(t) for t in tags],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST / — tạo tag mới
# ---------------------------------------------------------------------------

@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    data: TagCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])

    # Service raise DuplicateTagName (409) nếu trùng tên trong cùng owner
    tag = await service.create(db, owner_id, data)

    return TagResponse.model_validate(tag)


# ---------------------------------------------------------------------------
# PATCH /{tag_id} — cập nhật một phần tag
# ---------------------------------------------------------------------------

@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: str,
    data: TagUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Validate ObjectId trước khi gọi service — fail fast ở router layer
    oid = parse_object_id(tag_id)
    owner_id = ObjectId(current_user["_id"])

    # Service raise: TagNotFound (404), NotTagOwner (403), DuplicateTagName (409)
    updated = await service.update(db, oid, owner_id, data)

    return TagResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# DELETE /{tag_id} — xóa tag và dọn sạch khỏi contacts
# ---------------------------------------------------------------------------

@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(tag_id)
    owner_id = ObjectId(current_user["_id"])

    # Service xóa tag VÀ pull khỏi contacts đồng thời (asyncio.gather bên trong)
    await service.delete_with_bulk_pull(db, oid, owner_id)

    # 204 No Content — FastAPI tự không trả body nếu status_code=204