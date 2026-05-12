# from fastapi import APIRouter

# router = APIRouter(prefix="/activity", tags=["activity"])

# # Implementation: Phase 3 — W6 (Huy)
# # GET / → 200 OK → ActivityLogList  [Auth]  (query: page, limit)


"""
src/activity/router.py
----------------------
FastAPI router cho Activity module.
Expose 2 endpoints đọc activity logs — không có write endpoint vì
log_action() được gọi nội bộ từ các service khác, không phải từ client.
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.activity import service
from src.activity.schemas import ActivityLogList, ActivityLogResponse
from src.database import get_database                    # get_database nằm trong src/database.py, không phải src/core/
from src.core.pagination import PaginatedResponse
from src.auth.dependencies import get_current_user       # get_current_user nằm trong src/auth/dependencies.py

router = APIRouter(prefix="/activity", tags=["activity"])


# ---------------------------------------------------------------------------
# Helper — validate ObjectId từ query param
# Khác với path param (tag_id, event_id), contact_id ở đây là query string
# ---------------------------------------------------------------------------

def parse_optional_object_id(raw: str | None) -> ObjectId | None:
    """
    Convert str → ObjectId nếu có giá trị.
    Trả None nếu không có — cho phép filter contact_id là tùy chọn.
    Raise 422 nếu có giá trị nhưng format sai.
    """
    if raw is None:
        return None
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid contact_id format",
        )


# ---------------------------------------------------------------------------
# GET /activity — lấy toàn bộ activity logs của user, filter tùy chọn
# ---------------------------------------------------------------------------

@router.get("/", response_model=ActivityLogList)
async def list_all_activity(
    # Filter tùy chọn — không bắt buộc
    action: str | None = Query(
        default=None,
        description="Filter theo action: created | updated | enriched | tagged | deleted",
    ),
    contact_id: str | None = Query(
        default=None,
        description="Filter theo contact_id cụ thể (ObjectId string)",
    ),
    # Pagination — dùng skip/limit nhất quán với tất cả module khác
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Lấy tất cả activity logs thuộc về user đang đăng nhập.
    Hỗ trợ filter theo action và/hoặc contact_id.
    Kết quả sort created_at descending (mới nhất lên đầu).
    """
    owner_id = ObjectId(current_user["_id"])

    # Validate contact_id nếu có — 422 nếu format sai
    # Truyền vào service dưới dạng str vì service tự convert sang ObjectId
    logs, total = await service.list_all(
        db=db,
        owner_id=owner_id,
        action=action,
        contact_id=contact_id,   # str | None — service xử lý convert
        skip=skip,
        limit=limit,
    )

    # Dùng PaginatedResponse.build() để tự tính pages
    return PaginatedResponse.build(
        items=[ActivityLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /activity/contacts/{contact_id} — logs của một contact cụ thể
# Tách thành endpoint riêng thay vì dùng query param để URL rõ nghĩa hơn
# và dễ cache/index về sau
# ---------------------------------------------------------------------------

@router.get("/{contact_id}", response_model=ActivityLogList)
async def list_activity_by_contact(
    contact_id: str,                         # path param — bắt buộc
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Lấy activity logs của một contact cụ thể.
    Tự động kiểm tra ownership — user chỉ thấy logs của contacts mình sở hữu.
    """
    owner_id = ObjectId(current_user["_id"])

    # Validate ObjectId — fail fast tại router, không để lỗi lọt xuống service
    try:
        contact_oid = ObjectId(contact_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid contact_id format",
        )

    logs, total = await service.list_by_contact(
        db=db,
        contact_id=contact_oid,
        owner_id=owner_id,
        skip=skip,
        limit=limit,
    )

    return PaginatedResponse.build(
        items=[ActivityLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )