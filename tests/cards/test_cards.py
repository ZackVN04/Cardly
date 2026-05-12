import uuid

import pytest_asyncio

BASE = "/api/v1/cards"
PUBLIC_BASE = "/api/v1/public"
AUTH_BASE = "/api/v1/auth"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tcard_{s}",
        "email": f"tcard_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Cards Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH_BASE}/signup", json=payload)
    assert r.status_code == 201

    r2 = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {"token": token, **payload}

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


@pytest_asyncio.fixture
async def user_with_card(async_client, user):
    r = await async_client.post(
        f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"title": "Software Engineer", "is_public": True},
    )
    assert r.status_code == 201
    yield {**user, "card": r.json()}


# ---------------------------------------------------------------------------
# POST /cards/me
# ---------------------------------------------------------------------------

async def test_create_card_201(async_client, user):
    r = await async_client.post(
        f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"title": "Dev", "is_public": True},
    )
    assert r.status_code == 201


async def test_create_card_has_slug(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]), json={},
    )
    assert r.json()["slug"]


async def test_create_card_has_qr_code(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]), json={},
    )
    assert r.json()["qr_code_url"].startswith("data:image/png;base64,")


async def test_create_card_default_view_count_zero(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]), json={},
    )
    assert r.json()["view_count"] == 0


async def test_create_card_duplicate_409(async_client, user_with_card):
    r = await async_client.post(
        f"{BASE}/me",
        headers=_hdrs(user_with_card["token"]),
        json={},
    )
    assert r.status_code == 409


async def test_create_card_no_auth(async_client):
    r = await async_client.post(f"{BASE}/me", json={})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /cards/me
# ---------------------------------------------------------------------------

async def test_get_my_card_200(async_client, user_with_card):
    r = await async_client.get(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
    )
    assert r.status_code == 200


async def test_get_my_card_returns_correct_data(async_client, user_with_card):
    r = await async_client.get(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
    )
    assert r.json()["slug"] == user_with_card["card"]["slug"]


async def test_get_my_card_not_found(async_client, user):
    r = await async_client.get(
        f"{BASE}/me", headers=_hdrs(user["token"]),
    )
    assert r.status_code == 404


async def test_get_my_card_no_auth(async_client):
    r = await async_client.get(f"{BASE}/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /cards/me
# ---------------------------------------------------------------------------

async def test_update_card_200(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me",
        headers=_hdrs(user_with_card["token"]),
        json={"title": "Updated Title"},
    )
    assert r.status_code == 200


async def test_update_card_changes_field(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me",
        headers=_hdrs(user_with_card["token"]),
        json={"bio": "New bio text"},
    )
    assert r.json()["bio"] == "New bio text"


async def test_update_card_set_private(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me",
        headers=_hdrs(user_with_card["token"]),
        json={"is_public": False},
    )
    assert r.json()["is_public"] is False


async def test_update_card_not_found(async_client, user):
    r = await async_client.patch(
        f"{BASE}/me",
        headers=_hdrs(user["token"]),
        json={"bio": "x"},
    )
    assert r.status_code == 404


async def test_update_card_no_auth(async_client):
    r = await async_client.patch(f"{BASE}/me", json={"bio": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /cards/me
# ---------------------------------------------------------------------------

async def test_delete_card_204(async_client, user_with_card):
    r = await async_client.delete(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
    )
    assert r.status_code == 204


async def test_delete_card_removes_card(async_client, user_with_card):
    await async_client.delete(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
    )
    r = await async_client.get(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
    )
    assert r.status_code == 404


async def test_delete_card_not_found(async_client, user):
    r = await async_client.delete(
        f"{BASE}/me", headers=_hdrs(user["token"]),
    )
    assert r.status_code == 404


async def test_delete_card_no_auth(async_client):
    r = await async_client.delete(f"{BASE}/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /public/{slug}
# ---------------------------------------------------------------------------

async def test_get_public_card_200(async_client, user_with_card):
    slug = user_with_card["card"]["slug"]
    r = await async_client.get(f"{PUBLIC_BASE}/{slug}")
    assert r.status_code == 200


async def test_get_public_card_increments_view_count(async_client, user_with_card):
    slug = user_with_card["card"]["slug"]
    await async_client.get(f"{PUBLIC_BASE}/{slug}")
    r = await async_client.get(f"{PUBLIC_BASE}/{slug}")
    assert r.json()["view_count"] >= 2


async def test_get_public_card_not_found(async_client):
    r = await async_client.get(f"{PUBLIC_BASE}/nonexistent-slug-xyz")
    assert r.status_code == 404


async def test_get_public_card_private_returns_404(async_client, user_with_card):
    await async_client.patch(
        f"{BASE}/me",
        headers=_hdrs(user_with_card["token"]),
        json={"is_public": False},
    )
    slug = user_with_card["card"]["slug"]
    r = await async_client.get(f"{PUBLIC_BASE}/{slug}")
    assert r.status_code == 404


async def test_get_public_card_no_auth_required(async_client, user_with_card):
    slug = user_with_card["card"]["slug"]
    r = await async_client.get(f"{PUBLIC_BASE}/{slug}")
    assert r.status_code == 200
