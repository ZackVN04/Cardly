from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.contacts.schemas import ContactResponse
from src.core.rate_limit import limiter
from src.database import get_database
from src.scans import service
from src.scans.schemas import ConfirmScanRequest, ScanList, ScanPatch, ScanResponse

router = APIRouter(prefix="/scans", tags=["scans"])


def _parse_oid(raw: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} format",
        )


# ---------------------------------------------------------------------------
# GET / — danh sách scans của user, filter theo status
# ---------------------------------------------------------------------------

@router.get("/", response_model=ScanList)
async def list_scans(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(
        default=None,
        pattern="^(pending|processing|completed|confirmed|failed)$",
        description="Filter theo status",
    ),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    scans, total = await service.list_scans(
        db, owner_id, skip=skip, limit=limit, status_filter=status,
    )
    from src.core.pagination import PaginatedResponse
    return PaginatedResponse.build(
        items=[ScanResponse.model_validate(s) for s in scans],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST / — upload ảnh danh thiếp, trigger OCR async
# Rate limit: 10 lần/phút per IP
# ---------------------------------------------------------------------------

@router.post("/", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def upload_scan(
    request: Request,
    event_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Upload ảnh danh thiếp → OCR async → trả 202 ngay.
    Client poll GET /{id} mỗi 2s đến khi status='completed'.
    TODO W6: nhận UploadFile khi storage_client của Khanh sẵn sàng.
    """
    owner_id = ObjectId(current_user["_id"])

    event_oid: ObjectId | None = None
    if event_id:
        event_oid = _parse_oid(event_id, "event ID")

    # TODO W6: validate file type/size, upload to GCS, truyền image_url thực
    scan = await service.upload_scan(
        db,
        owner_id=owner_id,
        image_url="",   # placeholder — thay bằng GCS URL sau khi có storage_client
        event_id=event_oid,
    )
    return ScanResponse.model_validate(scan)


# ---------------------------------------------------------------------------
# GET /{scan_id} — lấy chi tiết scan, poll status
# Trả 408 nếu vẫn processing sau 30 giây
# ---------------------------------------------------------------------------

@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = _parse_oid(scan_id, "scan ID")
    owner_id = ObjectId(current_user["_id"])
    scan = await service.get_scan(db, oid, owner_id)
    return ScanResponse.model_validate(scan)


# ---------------------------------------------------------------------------
# PATCH /{scan_id} — sửa raw_text / extracted_data trước khi confirm
# Bị chặn nếu scan đã confirmed
# ---------------------------------------------------------------------------

@router.patch("/{scan_id}", response_model=ScanResponse)
async def patch_scan(
    scan_id: str,
    data: ScanPatch,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = _parse_oid(scan_id, "scan ID")
    owner_id = ObjectId(current_user["_id"])
    updated = await service.patch_scan(db, oid, owner_id, data)
    return ScanResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# POST /{scan_id}/confirm — xác nhận kết quả OCR, tạo contact
# Chỉ hoạt động khi status='completed'
# ---------------------------------------------------------------------------

@router.post("/{scan_id}/confirm", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def confirm_scan(
    scan_id: str,
    data: ConfirmScanRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = _parse_oid(scan_id, "scan ID")
    owner_id = ObjectId(current_user["_id"])
    contact = await service.confirm_scan(db, oid, owner_id, data)
    return ContactResponse.model_validate(contact)


# ---------------------------------------------------------------------------
# DELETE /{scan_id} — xóa scan record
# KHÔNG xóa contact đã tạo, KHÔNG xóa GCS image
# ---------------------------------------------------------------------------

@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    scan_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    oid = _parse_oid(scan_id, "scan ID")
    owner_id = ObjectId(current_user["_id"])
    await service.delete_scan(db, oid, owner_id)
