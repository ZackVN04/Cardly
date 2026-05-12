import uuid

import pytest_asyncio

from bson import ObjectId

BASE = "/api/v1/users"
AUTH_BASE = "/api/v1/auth"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tuser_{s}",
        "email": f"tuser_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Users Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH_BASE}/signup", json=payload)
    assert r.status_code == 201
    user_id = r.json()["id"]

    r2 = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {"token": token, "id": user_id, **payload}

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


@pytest_asyncio.fixture
async def other_user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH_BASE}/signup", json=payload)
    assert r.status_code == 201
    user_id = r.json()["id"]

    r2 = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {"token": token, "id": user_id, **payload}

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

async def test_get_me_200(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.status_code == 200


async def test_get_me_returns_username(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.json()["username"] == user["username"]


async def test_get_me_returns_full_name(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.json()["full_name"] == user["full_name"]


async def test_get_me_no_hashed_password(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert "hashed_password" not in r.json()


async def test_get_me_no_email(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert "email" not in r.json()


async def test_get_me_no_auth(async_client):
    r = await async_client.get(f"{BASE}/me")
    assert r.status_code == 401


async def test_get_me_invalid_token(async_client):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs("invalid.token.value"))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------

async def test_get_user_200(async_client, user, other_user):
    r = await async_client.get(
        f"{BASE}/{other_user['id']}",
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 200


async def test_get_user_returns_correct_username(async_client, user, other_user):
    r = await async_client.get(
        f"{BASE}/{other_user['id']}",
        headers=_hdrs(user["token"]),
    )
    assert r.json()["username"] == other_user["username"]


async def test_get_user_no_hashed_password(async_client, user, other_user):
    r = await async_client.get(
        f"{BASE}/{other_user['id']}",
        headers=_hdrs(user["token"]),
    )
    assert "hashed_password" not in r.json()


async def test_get_user_no_email(async_client, user, other_user):
    r = await async_client.get(
        f"{BASE}/{other_user['id']}",
        headers=_hdrs(user["token"]),
    )
    assert "email" not in r.json()


async def test_get_user_not_found(async_client, user):
    nonexistent_id = str(ObjectId())
    r = await async_client.get(
        f"{BASE}/{nonexistent_id}",
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 404


async def test_get_user_invalid_id(async_client, user):
    r = await async_client.get(
        f"{BASE}/not-a-valid-id",
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 404


async def test_get_user_no_auth(async_client, other_user):
    r = await async_client.get(f"{BASE}/{other_user['id']}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /users/search
# ---------------------------------------------------------------------------

async def test_search_users_200(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"]},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 200


async def test_search_users_finds_by_username(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"]},
        headers=_hdrs(user["token"]),
    )
    usernames = [item["username"] for item in r.json()["items"]]
    assert user["username"] in usernames


async def test_search_users_finds_by_full_name(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["full_name"]},
        headers=_hdrs(user["token"]),
    )
    assert r.json()["total"] >= 1


async def test_search_users_response_format(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"]},
        headers=_hdrs(user["token"]),
    )
    body = r.json()
    for key in ("items", "total", "skip", "limit", "pages"):
        assert key in body


async def test_search_users_no_results(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": "xyznonexistent123abc"},
        headers=_hdrs(user["token"]),
    )
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_search_users_case_insensitive(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"].upper()},
        headers=_hdrs(user["token"]),
    )
    usernames = [item["username"] for item in r.json()["items"]]
    assert user["username"] in usernames


async def test_search_users_missing_q(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 422


async def test_search_users_no_auth(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"]},
    )
    assert r.status_code == 401


async def test_search_users_pagination_format(async_client, user):
    r = await async_client.get(
        f"{BASE}/search",
        params={"q": user["username"], "page": 1, "limit": 5},
        headers=_hdrs(user["token"]),
    )
    assert r.json()["limit"] == 5
