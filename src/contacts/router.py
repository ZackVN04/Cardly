"""
src/contacts/router.py
----------------------
FastAPI router cho Contacts module.
Tất cả route đều yêu cầu xác thực — current_user inject qua Depends.
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.contacts import service
from src.contacts.schemas import (
    AddTagRequest,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
)
from src.core.pagination import PaginatedResponse
from src.database import get_database

router = APIRouter(prefix="/contacts", tags=["contacts"])


def parse_object_id(raw: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} format",
        )


# ---------------------------------------------------------------------------
# GET / — danh sách contacts với filter + phân trang
# ---------------------------------------------------------------------------

@router.get("/", response_model=ContactListResponse)
async def list_contacts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Tìm kiếm theo tên hoặc công ty"),
    tag_id: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    sort_by: str = Query(default="created_at", pattern="^(created_at|updated_at|full_name|company)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])

    contacts, total = await service.list_contacts(
        db, owner_id,
        skip=skip, limit=limit,
        q=q, tag_id=tag_id, event_id=event_id, sort_by=sort_by,
    )

    return PaginatedResponse.build(
        items=[ContactResponse.model_validate(c) for c in contacts],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST / — tạo contact mới
# ---------------------------------------------------------------------------

@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact = await service.create_contact(db, owner_id, data)
    return ContactResponse.model_validate(contact)


# ---------------------------------------------------------------------------
# GET /{contact_id} — lấy chi tiết một contact
# ---------------------------------------------------------------------------

@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(contact_id, "contact ID")
    owner_id = ObjectId(current_user["_id"])
    contact = await service.get_contact(db, oid, owner_id)
    return ContactResponse.model_validate(contact)


# ---------------------------------------------------------------------------
# PATCH /{contact_id} — cập nhật một phần contact
# ---------------------------------------------------------------------------

@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    data: ContactUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(contact_id, "contact ID")
    owner_id = ObjectId(current_user["_id"])
    updated = await service.update_contact(db, oid, owner_id, data)
    return ContactResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# DELETE /{contact_id} — xóa contact và cascade enrichment
# ---------------------------------------------------------------------------

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = parse_object_id(contact_id, "contact ID")
    owner_id = ObjectId(current_user["_id"])
    await service.delete_contact(db, oid, owner_id)


# ---------------------------------------------------------------------------
# POST /{contact_id}/tags — gắn tag vào contact
# ---------------------------------------------------------------------------

@router.post("/{contact_id}/tags", response_model=ContactResponse)
async def add_tag(
    contact_id: str,
    body: AddTagRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    contact_oid = parse_object_id(contact_id, "contact ID")
    tag_oid = parse_object_id(body.tag_id, "tag ID")
    owner_id = ObjectId(current_user["_id"])

    updated = await service.add_tag(db, contact_oid, owner_id, tag_oid)
    return ContactResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# DELETE /{contact_id}/tags/{tag_id} — gỡ tag khỏi contact
# ---------------------------------------------------------------------------

@router.delete("/{contact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tag(
    contact_id: str,
    tag_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    contact_oid = parse_object_id(contact_id, "contact ID")
    tag_oid = parse_object_id(tag_id, "tag ID")
    owner_id = ObjectId(current_user["_id"])

    await service.remove_tag(db, contact_oid, owner_id, tag_oid)
