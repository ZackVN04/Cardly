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


def _parse_oid(raw: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} format",
        )


# ---------------------------------------------------------------------------
# GET / — danh sách enrichment results của owner
# ---------------------------------------------------------------------------

@router.get("/", response_model=EnrichmentList)
async def list_enrichments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(
        default=None,
        pattern="^(pending|processing|completed|failed)$",
        description="Filter theo status",
    ),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    docs, total = await service.list_all(db, owner_id, skip=skip, limit=limit, status_filter=status)
    return PaginatedResponse.build(
        items=[EnrichmentResponse.model_validate(d) for d in docs],
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# POST /{contact_id} — trigger enrichment cho contact
# Rate limit: 5 lần/phút per IP
# ---------------------------------------------------------------------------

@router.post("/{contact_id}", response_model=EnrichmentResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def trigger_enrichment(
    request: Request,
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Trigger AI enrichment async → trả 202. Poll GET /{contact_id} để check status."""
    owner_id = ObjectId(current_user["_id"])
    contact_oid = _parse_oid(contact_id, "contact ID")
    doc = await service.trigger_enrichment(db, contact_oid, owner_id)
    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# GET /{contact_id} — lấy enrichment result của contact
# ---------------------------------------------------------------------------

@router.get("/{contact_id}", response_model=EnrichmentResponse)
async def get_enrichment(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = _parse_oid(contact_id, "contact ID")
    doc = await service.get_result(db, contact_oid, owner_id)
    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# PATCH /{contact_id} — manual edit enrichment result
# source được set thành 'manual' tự động
# ---------------------------------------------------------------------------

@router.patch("/{contact_id}", response_model=EnrichmentResponse)
async def update_enrichment(
    contact_id: str,
    data: EnrichmentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = _parse_oid(contact_id, "contact ID")
    doc = await service.update_manual(db, contact_oid, owner_id, data)
    return EnrichmentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# DELETE /{contact_id} — xóa enrichment result
# ---------------------------------------------------------------------------

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrichment(
    contact_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    owner_id = ObjectId(current_user["_id"])
    contact_oid = _parse_oid(contact_id, "contact ID")
    await service.delete_result(db, contact_oid, owner_id)
