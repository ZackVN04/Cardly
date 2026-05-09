"""
src/events/router.py
--------------------
FastAPI router cho Events module.
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.database import get_database
from src.core.pagination import PaginatedResponse          # generic wrapper {items, total, skip, limit}
from src.auth.dependencies import get_current_user         # dependency trả về user dict từ JWT
from src.events import service
from src.events.schemas import EventCreate, EventResponse, EventUpdate, EventWithContacts

router = APIRouter(prefix="/events", tags=["events"])


# ---------------------------------------------------------------------------
# Helper — validate ObjectId từ path param, fail fast tại router
# ---------------------------------------------------------------------------

def parse_object_id(raw: str) -> ObjectId:
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid event ID format",
        )


# ---------------------------------------------------------------------------
# GET / — danh sách events của user, sort event_date desc
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[EventResponse])
async def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])

    events, total = await service.list_events(db, owner_id, skip=skip, limit=limit)

    # Dùng .build() để tự tính pages — PaginatedResponse yêu cầu pages (không có default)
    return PaginatedResponse.build(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST / — tạo event mới
# ---------------------------------------------------------------------------

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    event = await service.create(db, owner_id, data)
    return EventResponse.model_validate(event)


# ---------------------------------------------------------------------------
# GET /{event_id} — lấy event kèm contacts phân trang ($lookup aggregation)
# ---------------------------------------------------------------------------

@router.get("/{event_id}", response_model=EventWithContacts)
async def get_event_with_contacts(
    event_id: str,
    contact_skip: int = Query(default=0, ge=0),
    contact_limit: int = Query(default=10, ge=1, le=50),  # max 50 contacts per page
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(event_id)
    owner_id = ObjectId(current_user["_id"])

    # Service raise EventNotFound (404) hoặc NotEventOwner (403)
    event = await service.get_with_contacts(
        db, oid, owner_id,
        contact_skip=contact_skip,
        contact_limit=contact_limit,
    )

    return EventWithContacts.model_validate(event)


# ---------------------------------------------------------------------------
# PATCH /{event_id} — cập nhật một phần event
# ---------------------------------------------------------------------------

@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    data: EventUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(event_id)
    owner_id = ObjectId(current_user["_id"])

    updated = await service.update(db, oid, owner_id, data)
    return EventResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# DELETE /{event_id} — xóa event, set event_id=None trên contacts liên kết
# ---------------------------------------------------------------------------

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(event_id)
    owner_id = ObjectId(current_user["_id"])

    # Service chạy delete + update_many song song qua asyncio.gather()
    await service.delete_with_cascade(db, oid, owner_id)

    # 204 — FastAPI tự bỏ body