import hashlib
import uuid
from datetime import datetime, timedelta

import pytest_asyncio

from src.auth.utils import create_reset_token
from src.core.config import settings
from src.database import get_database

BASE = "/api/v1/auth"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tauth_{s}",
        "email": f"tauth_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Auth Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 201

    r2 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {**payload, "token": token, "id": r.json()["id"]}

    await async_client.request(
        "DELETE", f"{BASE}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


# ---------------------------------------------------------------------------
# signup
# ---------------------------------------------------------------------------

async def test_signup_201(async_client):
    payload = _new_user()
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == payload["username"]
    assert body["email"] == payload["email"]
    assert "id" in body
    assert "hashed_password" not in body

    # cleanup
    r2 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    t = r2.json()["access_token"]
    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(t), json={"password": _PWD})


async def test_signup_username_stored_lowercase(async_client):
    payload = _new_user()
    payload["username"] = payload["username"].upper()
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 201
    assert r.json()["username"] == payload["username"].lower()

    r2 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"].lower(), "password": _PWD,
    })
    t = r2.json()["access_token"]
    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(t), json={"password": _PWD})


async def test_signup_duplicate_username(async_client, user):
    payload = _new_user()
    payload["username"] = user["username"]
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 409
    assert "Username" in r.json()["message"]


async def test_signup_duplicate_email(async_client, user):
    payload = _new_user()
    payload["email"] = user["email"]
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 409
    assert "Email" in r.json()["message"]


async def test_signup_invalid_email(async_client):
    payload = _new_user()
    payload["email"] = "not-an-email"
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 422


async def test_signup_password_too_short(async_client):
    payload = _new_user()
    payload["password"] = "short"
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 422


async def test_signup_username_special_chars(async_client):
    payload = _new_user()
    payload["username"] = "bad user!"
    r = await async_client.post(f"{BASE}/signup", json=payload)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# signin
# ---------------------------------------------------------------------------

async def test_signin_returns_access_token(async_client, user):
    r = await async_client.post(f"{BASE}/signin", json={
        "username": user["username"], "password": _PWD,
    })
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_signin_sets_refresh_cookie(async_client, user):
    r = await async_client.post(f"{BASE}/signin", json={
        "username": user["username"], "password": _PWD,
    })
    assert r.status_code == 200
    assert "refreshToken" in r.cookies


async def test_signin_wrong_password(async_client, user):
    r = await async_client.post(f"{BASE}/signin", json={
        "username": user["username"], "password": "WrongPass999",
    })
    assert r.status_code == 401


async def test_signin_unknown_username(async_client):
    r = await async_client.post(f"{BASE}/signin", json={
        "username": "nonexistent_xyz", "password": _PWD,
    })
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# signout
# ---------------------------------------------------------------------------

async def test_signout(async_client, user):
    r = await async_client.post(f"{BASE}/signout")
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------

async def test_refresh_with_cookie(async_client, user):
    r1 = await async_client.post(f"{BASE}/signin", json={
        "username": user["username"], "password": _PWD,
    })
    assert "refreshToken" in r1.cookies

    r2 = await async_client.post(f"{BASE}/refresh",
        cookies={"refreshToken": r1.cookies["refreshToken"]})
    assert r2.status_code == 200
    assert "access_token" in r2.json()


async def test_refresh_without_cookie(async_client):
    r = await async_client.post(f"{BASE}/refresh")
    assert r.status_code == 401


async def test_refresh_invalid_token(async_client):
    r = await async_client.post(f"{BASE}/refresh",
        cookies={"refreshToken": "garbage.invalid.token"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

async def test_get_me(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == user["username"]
    assert body["email"] == user["email"]
    assert "hashed_password" not in body


async def test_get_me_no_token(async_client):
    r = await async_client.get(f"{BASE}/me")
    assert r.status_code == 401


async def test_get_me_invalid_token(async_client):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs("garbage.token.value"))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------

async def test_update_me(async_client, user):
    r = await async_client.patch(f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"full_name": "Updated Name", "bio": "Hello world"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "Updated Name"
    assert body["bio"] == "Hello world"


async def test_update_me_partial(async_client, user):
    r = await async_client.patch(f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"bio": "Just bio"},
    )
    assert r.status_code == 200
    assert r.json()["bio"] == "Just bio"
    assert r.json()["full_name"] == user["full_name"]


async def test_update_me_no_token(async_client):
    r = await async_client.patch(f"{BASE}/me", json={"bio": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /me/password
# ---------------------------------------------------------------------------

async def test_change_password_success(async_client):
    payload = _new_user()
    await async_client.post(f"{BASE}/signup", json=payload)
    r = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r.json()["access_token"]

    r2 = await async_client.patch(f"{BASE}/me/password",
        headers=_hdrs(token),
        json={"old_password": _PWD, "new_password": "NewPass456"},
    )
    assert r2.status_code == 204

    # old password fails
    r3 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    assert r3.status_code == 401

    # new password works
    r4 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": "NewPass456",
    })
    assert r4.status_code == 200
    new_token = r4.json()["access_token"]

    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(new_token), json={"password": "NewPass456"})


async def test_change_password_wrong_current(async_client, user):
    r = await async_client.patch(f"{BASE}/me/password",
        headers=_hdrs(user["token"]),
        json={"old_password": "WrongPass999", "new_password": "NewPass456"},
    )
    assert r.status_code == 400


async def test_change_password_no_token(async_client):
    r = await async_client.patch(f"{BASE}/me/password",
        json={"old_password": _PWD, "new_password": "NewPass456"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# forgot-password
# ---------------------------------------------------------------------------

async def test_forgot_password_known_email(async_client, user):
    r = await async_client.post(f"{BASE}/forgot-password",
        json={"email": user["email"]})
    assert r.status_code == 200
    assert r.json() == {}


async def test_forgot_password_unknown_email(async_client):
    r = await async_client.post(f"{BASE}/forgot-password",
        json={"email": "nobody@cardly.dev"})
    assert r.status_code == 200
    assert r.json() == {}


# ---------------------------------------------------------------------------
# reset-password
# ---------------------------------------------------------------------------

async def test_reset_password_success(async_client):
    payload = _new_user()
    await async_client.post(f"{BASE}/signup", json=payload)

    token = create_reset_token(payload["email"], settings.JWT_SECRET)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=15)
    db = get_database()
    await db["users"].update_one(
        {"email": payload["email"]},
        {"$set": {"reset_token": token_hash, "reset_token_expiry": expiry}},
    )

    r = await async_client.post(f"{BASE}/reset-password",
        json={"token": token, "new_password": "ResetPass789"})
    assert r.status_code == 204

    r2 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": "ResetPass789",
    })
    assert r2.status_code == 200
    t = r2.json()["access_token"]
    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(t), json={"password": "ResetPass789"})


async def test_reset_password_invalid_token(async_client):
    r = await async_client.post(f"{BASE}/reset-password",
        json={"token": "not.a.valid.token", "new_password": "NewPass456"})
    assert r.status_code == 400


async def test_reset_password_replay_attack(async_client):
    payload = _new_user()
    await async_client.post(f"{BASE}/signup", json=payload)

    token = create_reset_token(payload["email"], settings.JWT_SECRET)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=15)
    db = get_database()
    await db["users"].update_one(
        {"email": payload["email"]},
        {"$set": {"reset_token": token_hash, "reset_token_expiry": expiry}},
    )

    # first use — success
    r1 = await async_client.post(f"{BASE}/reset-password",
        json={"token": token, "new_password": "ResetPass789"})
    assert r1.status_code == 204

    # second use — blocked
    r2 = await async_client.post(f"{BASE}/reset-password",
        json={"token": token, "new_password": "AnotherPass000"})
    assert r2.status_code == 400

    r3 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": "ResetPass789",
    })
    t = r3.json()["access_token"]
    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(t), json={"password": "ResetPass789"})


async def test_reset_token_cleared_after_use(async_client):
    payload = _new_user()
    await async_client.post(f"{BASE}/signup", json=payload)

    token = create_reset_token(payload["email"], settings.JWT_SECRET)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=15)
    db = get_database()
    await db["users"].update_one(
        {"email": payload["email"]},
        {"$set": {"reset_token": token_hash, "reset_token_expiry": expiry}},
    )

    await async_client.post(f"{BASE}/reset-password",
        json={"token": token, "new_password": "ResetPass789"})

    user_doc = await db["users"].find_one({"email": payload["email"]})
    assert user_doc["reset_token"] is None
    assert user_doc["reset_token_expiry"] is None

    r = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": "ResetPass789",
    })
    t = r.json()["access_token"]
    await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(t), json={"password": "ResetPass789"})


# ---------------------------------------------------------------------------
# DELETE /me
# ---------------------------------------------------------------------------

async def test_delete_me_success(async_client):
    payload = _new_user()
    await async_client.post(f"{BASE}/signup", json=payload)
    r = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r.json()["access_token"]

    r2 = await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(token), json={"password": _PWD})
    assert r2.status_code == 204

    # user no longer exists
    r3 = await async_client.post(f"{BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    assert r3.status_code == 401


async def test_delete_me_wrong_password(async_client, user):
    r = await async_client.request("DELETE", f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"password": "WrongPass999"},
    )
    assert r.status_code == 400


async def test_delete_me_no_token(async_client):
    r = await async_client.request("DELETE", f"{BASE}/me",
        json={"password": _PWD})
    assert r.status_code == 401
