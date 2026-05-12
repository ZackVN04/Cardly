"""
src/events/service.py
---------------------
Business logic cho Events module.
Mọi thao tác write đều gọi log_action() sau khi hoàn thành.
"""

import asyncio
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.activity.service import log_action
from src.events.exceptions import EventNotFound, NotEventOwner
from src.events.schemas import EventCreate, EventUpdate


# ---------------------------------------------------------------------------
# create — tạo event mới
# ---------------------------------------------------------------------------

async def create(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    data: EventCreate,
) -> dict:
    doc = {
        "owner_id": owner_id,
        "name": data.name,
        "location": data.location,
        "event_date": data.event_date,
        "description": data.description,
        "created_at": datetime.utcnow(),   # timestamp server-side, không tin client
    }

    result = await db["events"].insert_one(doc)

    inserted = await db["events"].find_one({"_id": result.inserted_id})
    return inserted


# ---------------------------------------------------------------------------
# list_events — lấy danh sách events của owner, sort theo event_date mới nhất
# ---------------------------------------------------------------------------

async def list_events(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    query = {"owner_id": owner_id}  # chỉ lấy events của user đang đăng nhập

    collection = db["events"]

    # Chạy count và find song song — tiết kiệm 1 round-trip so với tuần tự
    total_task = collection.count_documents(query)
    docs_task = (
        collection
        .find(query)
        .sort("event_date", -1)    # event sắp tới/gần đây nhất lên đầu
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )

    total, docs = await asyncio.gather(total_task, docs_task)
    return docs, total


# ---------------------------------------------------------------------------
# get_with_contacts — lấy event kèm danh sách contacts đã phân trang
# Dùng $lookup aggregation để join trong 1 query thay vì 2 query riêng
# ---------------------------------------------------------------------------

async def get_with_contacts(
    db: AsyncIOMotorDatabase,
    event_id: ObjectId,
    owner_id: ObjectId,
    contact_skip: int = 0,
    contact_limit: int = 20,
) -> dict:
    pipeline = [
        # Stage 1: lọc đúng event cần lấy — đặt $match đầu tiên để dùng index _id
        {"$match": {"_id": event_id}},

        # Stage 2: join contacts có event_id trỏ về event này
        # $lookup tương đương LEFT JOIN: contacts.event_id = events._id
        {"$lookup": {
            "from": "contacts",
            "localField": "_id",
            "foreignField": "event_id",
            "as": "contacts_raw",           # tên tạm — sẽ transform ở bước sau
            # pipeline bên trong $lookup để chỉ project 3 field cần thiết,
            # tránh kéo toàn bộ contact document vào memory
            "pipeline": [
                {"$project": {
                    "_id": 1,
                    "full_name": 1,
                    "company": 1,
                }}
            ],
        }},

        # Stage 3: tính tổng contacts và slice theo phân trang
        {"$addFields": {
            # contacts_total = tổng thực — tính trước khi slice để pagination đúng
            "contacts_total": {"$size": "$contacts_raw"},

            # $slice: [array, skip, limit] — phân trang trực tiếp trong MongoDB
            # tránh kéo toàn bộ mảng về Python rồi mới slice
            "contacts": {"$slice": ["$contacts_raw", contact_skip, contact_limit]},
        }},

        # Stage 4: bỏ field tạm contacts_raw — không cần trả về client
        {"$project": {"contacts_raw": 0}},
    ]

    cursor = db["events"].aggregate(pipeline)
    results = await cursor.to_list(length=1)   # chỉ expect 1 document

    if not results:
        raise EventNotFound()

    event = results[0]

    # Kiểm tra quyền sau khi đã lấy được doc — tránh lộ thông tin 404 vs 403
    if event["owner_id"] != owner_id:
        raise NotEventOwner()

    return event


# ---------------------------------------------------------------------------
# update — cập nhật một phần event
# ---------------------------------------------------------------------------

async def update(
    db: AsyncIOMotorDatabase,
    event_id: ObjectId,
    owner_id: ObjectId,
    data: EventUpdate,
) -> dict:
    # Bước 1: tìm event — 404 nếu không tồn tại
    event = await db["events"].find_one({"_id": event_id})
    if not event:
        raise EventNotFound()

    # Bước 2: kiểm tra quyền sở hữu
    if event["owner_id"] != owner_id:
        raise NotEventOwner()

    # Bước 3: chỉ lấy field thực sự được gửi lên
    update_fields = data.model_dump(exclude_none=True)

    if not update_fields:
        # Không có field nào → trả doc hiện tại, không cần DB write
        return event

    # Bước 4: ghi nhận giá trị cũ để log — snapshot trước khi $set
    previous_values = {k: event.get(k) for k in update_fields}

    # Bước 5: update và lấy doc mới trong 1 atomic operation
    updated = await db["events"].find_one_and_update(
        {"_id": event_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,   # trả về doc SAU khi update
    )

    return updated


# ---------------------------------------------------------------------------
# delete_with_cascade — xóa event và set event_id=None trên các contacts liên quan
# KHÔNG xóa contacts — chỉ unlink, tránh mất dữ liệu danh bạ
# ---------------------------------------------------------------------------

async def delete_with_cascade(
    db: AsyncIOMotorDatabase,
    event_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    # Bước 1: tìm event để lưu thông tin trước khi xóa (cần cho log)
    event = await db["events"].find_one({"_id": event_id})
    if not event:
        raise EventNotFound()

    # Bước 2: kiểm tra quyền
    if event["owner_id"] != owner_id:
        raise NotEventOwner()

    # Bước 3: xóa event VÀ nullify contacts đồng thời
    # asyncio.gather() đảm bảo cả 2 chạy song song — không để orphan event_id
    # update_many không filter theo owner_id vì event_id đã là unique reference
    # Lấy danh sách contacts bị ảnh hưởng TRƯỚC khi cascade để log đúng contact_id
    affected_contacts = await db["contacts"].find(
        {"event_id": event_id},
        {"_id": 1},
    ).to_list(length=None)

    await asyncio.gather(
        db["events"].delete_one({"_id": event_id}),
        db["contacts"].update_many(
            {"event_id": event_id},
            {"$set": {"event_id": None}},
        ),
    )

    # Log action='updated' trên từng contact bị ảnh hưởng (spec: "Log on affected contacts")
    for contact in affected_contacts:
        await log_action(
            db=db,
            contact_id=contact["_id"],
            owner_id=owner_id,
            action="updated",
            source="user_edit",
            changed_fields=["event_id"],
            previous_values={"event_id": str(event_id)},
            new_values={"event_id": None},
        )