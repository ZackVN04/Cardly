"""
src/enrichment/router.py
------------------------
FastAPI router cho Enrichment module.
Tất cả route (trừ GET /) đều yêu cầu xác thực — current_user inject qua Depends.
POST /{contact_id} có rate limit 5 request/phút per IP (slowapi).
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.core.pagination import PaginatedResponse
from src.core.rate_limit import limiter
from src.database import get_database
from src.enrichment import service
from src.enrichment.schemas import EnrichmentList, EnrichmentResponse, EnrichmentUpdate

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# ---------------------------------------------------------------------------
# Helper — validate ObjectId từ path param, fail fast tại router layer
# ---------------------------------------------------------------------------

def parse_object_id(raw: str) -> ObjectId:
    """
    Convert string path param → ObjectId.
    Raise 422 ngay tại router nếu format sai, không để lỗi rơi xuống service.
    """
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid contact ID format",
        )


# ---------------------------------------------------------------------------
# GET / — danh sách toàn bộ enrichment results của owner, có filter theo status
# ---------------------------------------------------------------------------

@router.get("/", response_model=EnrichmentList)
async def list_enrichments(
    skip: int = Query(default=0, ge=0, description="Số documents bỏ qua (offset)"),
    limit: int = Query(default=20, ge=1, le=100, description="Số items tối đa mỗi trang"),
    status_filter: str | None = Query(
        default=None,
        alias="status",                          # client vẫn gửi ?status=... như API doc
        pattern="^(pending|processing|completed|failed)$",
        description="Lọc theo trạng thái enrichment",
    ),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])

    # Service tự lọc theo owner — không bao giờ trả enrichment của người khác
    docs, total = await service.list_all(
        db, owner_id, skip=skip, limit=limit, status_filter=status_filter
    )

    return PaginatedResponse.build(
        items=[EnrichmentResponse.model_validate(d) for d in docs],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST /{contact_id} — kích hoạt enrichment bất đồng bộ cho một contact
# Rate limit: 5 request/phút per IP — tránh spam gọi Gemini API
# Trả 202 Accepted ngay lập tức, client poll GET /{contact_id} để check status
# ---------------------------------------------------------------------------

@router.post(
    "/{contact_id}",
    response_model=EnrichmentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/minute")
async def trigger_enrichment(
    request: Request,          # bắt buộc có Request để slowapi đọc IP cho rate limit
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = parse_object_id(contact_id)

    # Service raise:
    #   404 — contact không tồn tại
    #   403 — không phải owner của contact
    #   409 EnrichmentAlreadyRunning — đang có pipeline đang chạy (status=pending/processing)
    # Nếu đã có kết quả completed → archive vào activity_log rồi chạy lại (re-run flow)
    doc = await service.trigger_enrichment(db, contact_oid, owner_id)

    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# GET /{contact_id} — lấy enrichment result hiện tại của một contact
# Client poll endpoint này mỗi 2s cho đến khi status ∈ {completed, failed}
# Tối đa poll 60s (AI pipeline chậm hơn OCR)
# ---------------------------------------------------------------------------

@router.get("/{contact_id}", response_model=EnrichmentResponse)
async def get_enrichment(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = parse_object_id(contact_id)

    # Service raise:
    #   404 — contact không tồn tại hoặc chưa trigger enrichment
    #   403 — không phải owner
    doc = await service.get_result(db, contact_oid, owner_id)

    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# PATCH /{contact_id} — chỉnh sửa thủ công enrichment result
# source tự động được set thành 'manual' bên trong service
# Chỉ cần gửi các field muốn thay đổi (partial update)
# ---------------------------------------------------------------------------

@router.patch("/{contact_id}", response_model=EnrichmentResponse)
async def update_enrichment(
    contact_id: str,
    data: EnrichmentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = parse_object_id(contact_id)

    # Service raise:
    #   404 — enrichment result chưa tồn tại (chưa trigger) hoặc contact không tồn tại
    #   403 — không phải owner
    # Service tự ghi activity_log với changed_fields chính xác (chỉ các field được gửi)
    doc = await service.update_manual(db, contact_oid, owner_id, data)

    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# DELETE /{contact_id} — xóa enrichment result, ghi log snapshot trước khi xóa
# ---------------------------------------------------------------------------

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrichment(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = parse_object_id(contact_id)

    # Service raise:
    #   404 — enrichment result không tồn tại hoặc contact không tồn tại
    #   403 — không phải owner
    # Service ghi activity_log với previous_values = snapshot đầy đủ TRƯỚC khi xóa
    await service.delete_result(db, contact_oid, owner_id)

    # 204 No Content — FastAPI tự không trả body
