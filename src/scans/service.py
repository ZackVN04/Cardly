import asyncio
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.activity.service import log_action
from src.tags.service import generate_auto_tags
from src.scans.exceptions import (
    CannotEditConfirmedScan,
    NotScanOwner,
    OCRFailed,
    ScanAlreadyConfirmed,
    ScanNotCompleted,
    ScanNotFound,
    ScanStillProcessing,
)
from src.scans.schemas import ConfirmScanRequest, ScanPatch

_PROCESSING_TIMEOUT = timedelta(seconds=30)


async def list_scans(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    skip: int = 0,
    limit: int = 20,
    status_filter: str | None = None,
) -> tuple[list[dict], int]:
    query: dict = {"owner_id": owner_id}
    if status_filter:
        query["status"] = status_filter

    collection = db["business_card_scans"]
    total_task = collection.count_documents(query)
    docs_task = (
        collection
        .find(query)
        .sort("scanned_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )

    total, docs = await asyncio.gather(total_task, docs_task)
    return docs, total


async def get_scan(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    owner_id: ObjectId,
) -> dict:
    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    if not scan:
        raise ScanNotFound()
    if scan["owner_id"] != owner_id:
        raise NotScanOwner()

    # 422 khi OCR thất bại — client phải dừng poll và thông báo lỗi cho user
    if scan["status"] == "failed":
        raise OCRFailed()

    # 408 khi scan vẫn processing quá 30 giây — client phải retry sau
    if (
        scan["status"] == "processing"
        and datetime.utcnow() - scan["scanned_at"] > _PROCESSING_TIMEOUT
    ):
        raise ScanStillProcessing()

    return scan


async def patch_scan(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    owner_id: ObjectId,
    data: ScanPatch,
) -> dict:
    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    if not scan:
        raise ScanNotFound()
    if scan["owner_id"] != owner_id:
        raise NotScanOwner()
    if scan["status"] == "confirmed":
        raise CannotEditConfirmedScan()

    update_fields: dict = {}

    if data.raw_text is not None:
        update_fields["raw_text"] = data.raw_text

    if data.extracted_data is not None:
        # Merge vào existing extracted_data — chỉ ghi đè field được gửi lên
        # Cho phép user sửa từng field riêng lẻ mà không mất dữ liệu OCR khác
        existing = scan.get("extracted_data") or {}
        patch_dict = data.extracted_data.model_dump(exclude_none=True)
        update_fields["extracted_data"] = {**existing, **patch_dict}

    if not update_fields:
        return scan

    updated = await db["business_card_scans"].find_one_and_update(
        {"_id": scan_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER,
    )
    return updated


async def delete_scan(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    owner_id: ObjectId,
) -> None:
    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    if not scan:
        raise ScanNotFound()
    if scan["owner_id"] != owner_id:
        raise NotScanOwner()

    await db["business_card_scans"].delete_one({"_id": scan_id})

    blob_name = scan.get("image_blob_name")
    if blob_name:
        import asyncio as _asyncio
        from src.uploads.storage_client import delete_from_gcs
        _asyncio.create_task(delete_from_gcs(blob_name))


async def confirm_scan(
    db: AsyncIOMotorDatabase,
    scan_id: ObjectId,
    owner_id: ObjectId,
    data: ConfirmScanRequest,
) -> dict:
    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    if not scan:
        raise ScanNotFound()
    if scan["owner_id"] != owner_id:
        raise NotScanOwner()
    if scan["status"] == "confirmed":
        raise ScanAlreadyConfirmed()
    if scan["status"] != "completed":
        raise ScanNotCompleted()

    # Nếu không truyền confirmed_data → tự dùng extracted_data từ scan
    if data.confirmed_data is None:
        ed = scan.get("extracted_data") or {}
        full_name = ed.get("full_name") or ""
        if not full_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="full_name is required — scan extracted_data has no full_name",
            )
        from src.scans.schemas import ConfirmedData
        data = data.model_copy(update={"confirmed_data": ConfirmedData(
            full_name=full_name,
            position=ed.get("position"),
            company=ed.get("company"),
            phone=ed.get("phone"),
            email=ed.get("email"),
            website=ed.get("website"),
            linkedin_url=ed.get("linkedin_url"),
            facebook_url=ed.get("facebook_url"),
            address=ed.get("address"),
        )})

    # Validate tag_ids format
    tag_oids: list[ObjectId] = []
    for tid in data.tag_ids:
        try:
            tag_oids.append(ObjectId(tid))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid tag ID: {tid}",
            )

    # Verify tất cả tags thuộc về owner — chặn gán tag của người khác
    if tag_oids:
        owned = await db["tags"].count_documents({
            "_id": {"$in": tag_oids},
            "owner_id": owner_id,
        })
        if owned != len(tag_oids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more tags do not belong to you",
            )

    # Validate event_id format
    event_oid: ObjectId | None = None
    if data.event_id:
        try:
            event_oid = ObjectId(data.event_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid event_id format",
            )

    now = datetime.utcnow()
    cd = data.confirmed_data

    contact_doc = {
        "owner_id": owner_id,
        "scan_id": scan_id,
        "event_id": event_oid,
        "tag_ids": tag_oids,
        "full_name": cd.full_name,
        "position": cd.position,
        "company": cd.company,
        "phone": cd.phone,
        "email": cd.email,
        "website": cd.website,
        "linkedin_url": cd.linkedin_url,
        "facebook_url": cd.facebook_url,
        "address": cd.address,
        "notes": data.notes,
        "created_at": now,
        "updated_at": now,
    }

    # Contact insert trước — nếu lỗi thì scan vẫn 'completed', user retry được
    contact_result = await db["contacts"].insert_one(contact_doc)

    # Đánh dấu scan đã confirmed sau khi contact tạo thành công
    await db["business_card_scans"].update_one(
        {"_id": scan_id},
        {"$set": {"status": "confirmed"}},
    )

    contact = await db["contacts"].find_one({"_id": contact_result.inserted_id})

    await log_action(
        db=db,
        contact_id=contact_result.inserted_id,
        owner_id=owner_id,
        action="created",
        source="scan",
        new_values={
            "full_name": cd.full_name,
            "company": cd.company,
            "scan_id": str(scan_id),
        },
    )

    auto_tag_ids = await generate_auto_tags(db, owner_id, contact)
    if auto_tag_ids:
        await db["contacts"].update_one(
            {"_id": contact_result.inserted_id},
            {"$addToSet": {"tag_ids": {"$each": auto_tag_ids}}},
        )
        contact = await db["contacts"].find_one({"_id": contact_result.inserted_id})

    return contact


async def upload_scan_multi_page(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    image_urls: list[str],
    image_blob_names: list[str] | None = None,
    event_id: ObjectId | None = None,
) -> dict:
    doc = {
        "owner_id": owner_id,
        "event_id": event_id,
        "image_url": image_urls[0],
        "image_blob_name": (image_blob_names or [None])[0],
        "status": "processing",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow(),
    }

    result = await db["business_card_scans"].insert_one(doc)

    from src.scans.ocr_client import run_ocr_multi_page
    asyncio.create_task(run_ocr_multi_page(db, result.inserted_id, image_urls))

    return await db["business_card_scans"].find_one({"_id": result.inserted_id})


async def upload_scan(
    db: AsyncIOMotorDatabase,
    owner_id: ObjectId,
    image_url: str,
    image_blob_name: str | None = None,
    event_id: ObjectId | None = None,
) -> dict:
    doc = {
        "owner_id": owner_id,
        "event_id": event_id,
        "image_url": image_url,
        "image_blob_name": image_blob_name,
        "status": "processing",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow(),
    }

    result = await db["business_card_scans"].insert_one(doc)

    if image_url:
        from src.scans.ocr_client import run_ocr
        asyncio.create_task(run_ocr(db, result.inserted_id, image_url))

    return await db["business_card_scans"].find_one({"_id": result.inserted_id})
