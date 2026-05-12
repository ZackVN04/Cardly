import math

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.core.pagination import paginate_query
from src.database import get_database
from src.users import service
from src.users.schemas import UserPublic, UserSearchList

router = APIRouter(prefix="/users", tags=["users"])


def _to_public(user: dict) -> UserPublic:
    return UserPublic(
        id=str(user["_id"]),
        username=user["username"],
        full_name=user.get("full_name") or "",
        avatar_url=user.get("avatar_url"),
        bio=user.get("bio"),
    )


@router.get("/me", response_model=UserPublic)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await service.get_public_profile(db, current_user["_id"])
    return _to_public(user)


@router.get("/search", response_model=UserSearchList)
async def search_users(
    q: str = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    skip, limit_val = paginate_query(page, limit)
    items, total = await service.search_users(db, q, skip, limit_val)
    pages = math.ceil(total / limit_val) if limit_val > 0 else 1
    return UserSearchList(
        items=[_to_public(u) for u in items],
        total=total,
        skip=skip,
        limit=limit_val,
        pages=pages,
    )


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await service.get_public_profile(db, user_id)
    return _to_public(user)
