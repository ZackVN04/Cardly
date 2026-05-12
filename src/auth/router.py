"""
src/auth/router.py
------------------
FastAPI router cho Auth module.
"""

from bson import ObjectId
from fastapi import APIRouter, Cookie, Depends, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth import service
from src.auth.dependencies import get_current_user
from src.auth.schemas import (
    DeleteAccountReq,
    ForgotPasswordReq,
    PasswordChange,
    ResetPasswordReq,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from src.database import get_database

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refreshToken"
_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 ngày tính bằng giây


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,       # JS không đọc được — bảo vệ XSS
        samesite="lax",
        secure=False,        # True khi deploy HTTPS
        max_age=_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, httponly=True, samesite="lax")


# ---------------------------------------------------------------------------
# POST /signup — đăng ký tài khoản mới
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    data: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await service.register(db, data)
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# POST /signin — đăng nhập, trả access token + set refresh cookie
# ---------------------------------------------------------------------------

@router.post("/signin", response_model=TokenResponse)
async def signin(
    data: UserLogin,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await service.authenticate(db, data.username, data.password)
    access, refresh = service.create_tokens(str(user["_id"]))
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


# ---------------------------------------------------------------------------
# POST /signout — đăng xuất, xóa refresh cookie
# ---------------------------------------------------------------------------

@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout(response: Response):
    _clear_refresh_cookie(response)


# ---------------------------------------------------------------------------
# POST /refresh — dùng refresh cookie để lấy access token mới
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    from src.auth.exceptions import TokenInvalid
    if not refresh_cookie:
        raise TokenInvalid()

    access = service.refresh_token(refresh_cookie)

    # Rotate: issue new access token — refresh cookie giữ nguyên
    return TokenResponse(access_token=access)


# ---------------------------------------------------------------------------
# GET /me — lấy thông tin user hiện tại
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await service.get_me(db, ObjectId(current_user["_id"]))
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# PATCH /me — cập nhật profile
# ---------------------------------------------------------------------------

@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updated = await service.update_profile(db, ObjectId(current_user["_id"]), data)
    return UserResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# PATCH /me/password — đổi mật khẩu
# ---------------------------------------------------------------------------

@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.change_password(db, ObjectId(current_user["_id"]), data)


# ---------------------------------------------------------------------------
# POST /forgot-password — yêu cầu reset password
# ---------------------------------------------------------------------------

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    data: ForgotPasswordReq,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.forgot_password(db, data.email)
    return {}  # luôn trả {} — không tiết lộ email có tồn tại không


# ---------------------------------------------------------------------------
# POST /reset-password — đặt lại mật khẩu bằng reset token
# ---------------------------------------------------------------------------

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    data: ResetPasswordReq,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.reset_password(db, data)


# ---------------------------------------------------------------------------
# DELETE /me — xóa tài khoản (cần xác nhận mật khẩu)
# ---------------------------------------------------------------------------

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    data: DeleteAccountReq,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.delete_account(db, ObjectId(current_user["_id"]), data)
    _clear_refresh_cookie(response)
