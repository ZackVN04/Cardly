from bson import ObjectId
from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth.dependencies import get_current_user
from src.cards import service
from src.cards.schemas import (
    DigitalCardCreate,
    DigitalCardResponse,
    DigitalCardUpdate,
    PublicCardResponse,
)
from src.database import get_database

router = APIRouter(prefix="/cards", tags=["cards"])
public_router = APIRouter(prefix="/public", tags=["public"])


@router.get("/me", response_model=DigitalCardResponse)
async def get_my_card(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    card = await service.get_my_card(db, ObjectId(current_user["_id"]))
    return DigitalCardResponse.model_validate(card)


@router.post("/me", response_model=DigitalCardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    data: DigitalCardCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    card = await service.create_card(db, ObjectId(current_user["_id"]), data)
    return DigitalCardResponse.model_validate(card)


@router.patch("/me", response_model=DigitalCardResponse)
async def update_card(
    data: DigitalCardUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    card = await service.update_card(db, ObjectId(current_user["_id"]), data)
    return DigitalCardResponse.model_validate(card)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.delete_card(db, ObjectId(current_user["_id"]))


@public_router.get("/{slug}", response_model=PublicCardResponse)
async def get_public_card(
    slug: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    card = await service.get_public_card(db, slug)
    return PublicCardResponse.model_validate(card)
