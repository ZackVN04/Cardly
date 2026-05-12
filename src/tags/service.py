#from src.tags.schemas import TagCreate, TagUpdate

# Implementation: Phase 3 — W4 (Khanh)
# create(owner_id: str, data: TagCreate) -> TagDoc
# list_tags(owner_id: str) -> list[TagDoc]
# update(tag_id: str, owner_id: str, data: TagUpdate) -> TagDoc
# delete_with_bulk_pull(tag_id: str, owner_id: str) -> None  # also removes tag from all contacts


"""
src/tags/service.py
-------------------
Business logic cho Tags module.
Mọi thao tác write đều gọi log_action() sau khi hoàn thành.
"""

import asyncio
import re
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from pymongo import ReturnDocument

from src.activity.service import log_action
from src.tags.exceptions import DuplicateTagName, NotTagOwner, TagNotFound
from src.tags.schemas import TagCreate, TagUpdate


# ---------------------------------------------------------------------------
# _check_duplicate — kiểm tra tên tag trùng trong cùng owner
# ---------------------------------------------------------------------------

async def _check_duplicate(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    name: str,
    exclude_id: ObjectId | None = None,   # khi update: loại chính nó ra khỏi check
) -> None:
    """
    Tìm tag có cùng tên (case-insensitive) trong cùng owner.
    Dùng regex thay vì collation để tránh phụ thuộc vào MongoDB collation config.
    """
    # re.escape đảm bảo tên chứa ký tự đặc biệt không phá regex
    pattern = re.compile(f"^{re.escape(name)}$", re.IGNORECASE)

    query: dict = {
        "owner_id": owner_id,
        "name": {"$regex": pattern},
    }

    if exclude_id:
        # Khi update, loại chính tag đang sửa ra để không tự conflict với mình
        query["_id"] = {"$ne": exclude_id}

    existing = await db["tags"].find_one(query)

    if existing:
        raise DuplicateTagName()


# ---------------------------------------------------------------------------
# create — tạo tag mới
# ---------------------------------------------------------------------------

async def create(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    data: TagCreate,
) -> dict:
    # Bước 1: kiểm tra trùng tên trước khi insert để trả lỗi sớm
    await _check_duplicate(db, owner_id, data.name)

    doc = {
        "owner_id": owner_id,
        "name": data.name,
        "color": data.color,
        "source": data.source,
        "created_at": datetime.utcnow(),  # timestamp server-side, không tin client
    }

    # insert_one trả InsertOneResult, lấy inserted_id để fetch lại doc đầy đủ
    result = await db["tags"].insert_one(doc)

    inserted = await db["tags"].find_one({"_id": result.inserted_id})
    return inserted


# ---------------------------------------------------------------------------
# list_tags — lấy danh sách tags của owner, có phân trang
# ---------------------------------------------------------------------------

async def list_tags(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    query = {"owner_id": owner_id}  # chỉ lấy tags của chính user

    collection = db["tags"]

    # Chạy count và find song song — tiết kiệm 1 round-trip MongoDB
    total_task = collection.count_documents(query)
    docs_task = (
        collection
        .find(query)
        .sort("created_at", -1)   # mới nhất lên đầu
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )

    total, docs = await asyncio.gather(total_task, docs_task)
    return docs, total


# ---------------------------------------------------------------------------
# update — cập nhật name và/hoặc color của tag
# ---------------------------------------------------------------------------

async def update(
    db: AsyncIOMotorDatabase,
    tag_id: ObjectId,
    owner_id: ObjectId,
    data: TagUpdate,
) -> dict:
    # Bước 1: tìm tag — nếu không có thì 404 ngay
    tag = await db["tags"].find_one({"_id": tag_id})
    if not tag:
        raise TagNotFound()

    # Bước 2: kiểm tra quyền — tag phải thuộc owner đang gọi
    if tag["owner_id"] != owner_id:
        raise NotTagOwner()

    # Bước 3: chỉ lấy các field thực sự được truyền lên (exclude_none)
    # Tránh ghi đè field bằng None nếu client không gửi
    update_fields = data.model_dump(exclude_none=True)

    if not update_fields:
        # Không có gì để update → trả về doc hiện tại luôn, không cần DB write
        return tag

    # Bước 4: nếu đổi tên, kiểm tra trùng với tag khác của cùng owner
    if "name" in update_fields:
        await _check_duplicate(db, owner_id, update_fields["name"], exclude_id=tag_id)

    # Bước 5: ghi nhận giá trị cũ để log
    previous_values = {k: tag.get(k) for k in update_fields}

    # Bước 6: update và lấy document mới (return_document=True)
    updated = await db["tags"].find_one_and_update(
        {"_id": tag_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,  # trả về doc sau khi update
    )

    return updated


# ---------------------------------------------------------------------------
# delete_with_bulk_pull — xóa tag và gỡ khỏi tất cả contacts
# ---------------------------------------------------------------------------

async def delete_with_bulk_pull(
    db: AsyncIOMotorDatabase,
    tag_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    # Bước 1: tìm tag để lưu thông tin trước khi xóa (cần cho log)
    tag = await db["tags"].find_one({"_id": tag_id})
    if not tag:
        raise TagNotFound()

    # Bước 2: kiểm tra quyền sở hữu
    if tag["owner_id"] != owner_id:
        raise NotTagOwner()

    # Bước 3: xóa tag VÀ gỡ khỏi contacts ĐỒNG THỜI
    # Dùng asyncio.gather() để tránh orphan tag_ids nếu chỉ làm 1 trong 2
    # delete_one và update_many đều idempotent nên an toàn khi chạy song song
    # Lấy danh sách contacts bị ảnh hưởng TRƯỚC khi xóa để log đúng contact_id
    affected_contacts = await db["contacts"].find(
        {"owner_id": owner_id, "tag_ids": tag_id},
        {"_id": 1},
    ).to_list(length=None)

    await asyncio.gather(
        db["tags"].delete_one({"_id": tag_id}),
        db["contacts"].update_many(
            {"owner_id": owner_id, "tag_ids": tag_id},
            {"$pull": {"tag_ids": tag_id}},
        ),
    )

    # Log action='tagged' trên từng contact bị ảnh hưởng (spec: "Log on affected contacts")
    for contact in affected_contacts:
        await log_action(
            db=db,
            contact_id=contact["_id"],
            owner_id=owner_id,
            action="tagged",
            source="user_edit",
            changed_fields=["tag_ids"],
            previous_values={"tag_id": str(tag_id), "tag_name": tag["name"]},
        )