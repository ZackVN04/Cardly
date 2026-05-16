import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio

from src.database import get_database

BASE = "/api/v1/cards"
PUBLIC_BASE = "/api/v1/public"
AUTH_BASE = "/api/v1/auth"
_PWD = "TestPass123"
_QR_URL = "https://storage.googleapis.com/cardly/qr_codes/test.png"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tcard_{s}",
        "email": f"tcard_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Cards Test User",
    }


def _new_slug() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


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
    yield {"token": token, "id": r.json()["id"], **payload}
    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(token), json={"password": _PWD},
    )


@pytest_asyncio.fixture
async def user_with_card(async_client, user):
    slug = _new_slug()
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me",
            headers=_hdrs(user["token"]),
            json={
                "slug": slug,
                "display_name": "Test User",
                "title": "Engineer",
                "is_public": True,
            },
        )
    assert r.status_code == 201
    yield {**user, "card": r.json(), "slug": slug}


# ---------------------------------------------------------------------------
# POST /cards/me
# ---------------------------------------------------------------------------

async def test_create_card_201(async_client, user):
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user["token"]),
            json={"slug": _new_slug(), "display_name": "My Card"},
        )
    assert r.status_code == 201


async def test_create_card_response_fields(async_client, user):
    slug = _new_slug()
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user["token"]),
            json={"slug": slug, "display_name": "My Card", "title": "CEO"},
        )
    body = r.json()
    assert body["slug"] == slug
    assert body["display_name"] == "My Card"
    assert body["title"] == "CEO"
    assert body["qr_code_url"] == _QR_URL
    assert body["view_count"] == 0
    assert body["is_public"] is True
    assert "id" in body
    assert "user_id" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_card_missing_slug_422(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"display_name": "My Card"},
    )
    assert r.status_code == 422


async def test_create_card_missing_display_name_422(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"slug": _new_slug()},
    )
    assert r.status_code == 422


async def test_create_card_invalid_slug_uppercase_422(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"slug": "Invalid-Slug", "display_name": "x"},
    )
    assert r.status_code == 422


async def test_create_card_invalid_slug_starts_with_hyphen_422(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"slug": "-invalid", "display_name": "x"},
    )
    assert r.status_code == 422


async def test_create_card_invalid_slug_too_short_422(async_client, user):
    # regex requires first char + at least 2 more = min 3 chars total
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"slug": "ab", "display_name": "x"},
    )
    assert r.status_code == 422


async def test_create_card_invalid_slug_with_space_422(async_client, user):
    r = await async_client.post(
        f"{BASE}/me", headers=_hdrs(user["token"]),
        json={"slug": "my slug", "display_name": "x"},
    )
    assert r.status_code == 422


async def test_create_card_slug_taken_409(async_client, user_with_card):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(other_token),
            json={"slug": user_with_card["slug"], "display_name": "Other User"},
        )
    assert r.status_code == 409

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_create_card_user_already_has_card_409(async_client, user_with_card):
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
            json={"slug": _new_slug(), "display_name": "Second Card"},
        )
    assert r.status_code == 409


async def test_create_card_with_links(async_client, user):
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user["token"]),
            json={
                "slug": _new_slug(),
                "display_name": "Linked User",
                "links": {
                    "phone": "0901234567",
                    "linkedin": "linkedin.com/in/test",
                    "zalo": "0901234567",
                },
            },
        )
    assert r.status_code == 201
    body = r.json()
    assert body["links"]["phone"] == "0901234567"
    assert body["links"]["linkedin"] == "linkedin.com/in/test"


async def test_create_card_with_highlights(async_client, user):
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user["token"]),
            json={
                "slug": _new_slug(),
                "display_name": "Speaker",
                "highlights": ["Founded TechCorp 2020", "Series A"],
            },
        )
    assert r.status_code == 201
    assert "Founded TechCorp 2020" in r.json()["highlights"]


async def test_create_card_default_is_public_true(async_client, user):
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(user["token"]),
            json={"slug": _new_slug(), "display_name": "x"},
        )
    assert r.json()["is_public"] is True


async def test_create_card_no_auth_401(async_client):
    r = await async_client.post(
        f"{BASE}/me", json={"slug": _new_slug(), "display_name": "x"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /cards/me
# ---------------------------------------------------------------------------

async def test_get_my_card_200(async_client, user_with_card):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    assert r.status_code == 200


async def test_get_my_card_returns_correct_data(async_client, user_with_card):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    body = r.json()
    assert body["slug"] == user_with_card["slug"]
    assert body["display_name"] == "Test User"
    assert body["title"] == "Engineer"


async def test_get_my_card_404_when_no_card(async_client, user):
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.status_code == 404


async def test_get_my_card_isolation(async_client, user_with_card):
    # Another user with no card gets 404, not user_with_card's card
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r = await async_client.get(f"{BASE}/me", headers=_hdrs(other_token))
    assert r.status_code == 404

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_get_my_card_no_auth_401(async_client):
    r = await async_client.get(f"{BASE}/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /cards/me
# ---------------------------------------------------------------------------

async def test_update_card_200(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"title": "Updated Title"},
    )
    assert r.status_code == 200


async def test_update_card_changes_field(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"bio": "New bio text"},
    )
    assert r.json()["bio"] == "New bio text"


async def test_update_card_set_private(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"is_public": False},
    )
    assert r.json()["is_public"] is False


async def test_update_card_slug_change_regenerates_qr(async_client, user_with_card):
    new_slug = _new_slug()
    new_qr = "https://storage.googleapis.com/cardly/qr_codes/new.png"
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=new_qr)):
        r = await async_client.patch(
            f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
            json={"slug": new_slug},
        )
    body = r.json()
    assert body["slug"] == new_slug
    assert body["qr_code_url"] == new_qr
    assert body["qr_code_url"] != user_with_card["card"]["qr_code_url"]


async def test_update_card_same_slug_does_not_regenerate_qr(async_client, user_with_card):
    original_qr = user_with_card["card"]["qr_code_url"]
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"slug": user_with_card["slug"]},
    )
    assert r.json()["qr_code_url"] == original_qr


async def test_update_card_slug_invalid_format_422(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"slug": "BAD_SLUG"},
    )
    assert r.status_code == 422


async def test_update_card_slug_taken_409(async_client, user_with_card):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    other_slug = _new_slug()
    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        await async_client.post(
            f"{BASE}/me", headers=_hdrs(other_token),
            json={"slug": other_slug, "display_name": "Other"},
        )

    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.patch(
            f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
            json={"slug": other_slug},
        )
    assert r.status_code == 409

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_update_card_empty_body_returns_unchanged(async_client, user_with_card):
    original = user_with_card["card"]
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]), json={},
    )
    assert r.status_code == 200
    assert r.json()["slug"] == original["slug"]
    assert r.json()["display_name"] == original["display_name"]


async def test_update_card_updates_links(async_client, user_with_card):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"links": {"phone": "0909090909", "website": "techcorp.vn"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["links"]["phone"] == "0909090909"
    assert body["links"]["website"] == "techcorp.vn"


async def test_update_card_404_when_no_card(async_client, user):
    r = await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user["token"]), json={"bio": "x"},
    )
    assert r.status_code == 404


async def test_update_card_no_auth_401(async_client):
    r = await async_client.patch(f"{BASE}/me", json={"bio": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /cards/me
# ---------------------------------------------------------------------------

async def test_delete_card_204(async_client, user_with_card):
    r = await async_client.delete(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    assert r.status_code == 204


async def test_delete_card_removes_card(async_client, user_with_card):
    await async_client.delete(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    assert r.status_code == 404


async def test_delete_card_frees_slug(async_client, user_with_card):
    slug = user_with_card["slug"]
    await async_client.delete(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))

    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    with patch("src.cards.service.generate_qr", AsyncMock(return_value=_QR_URL)):
        r = await async_client.post(
            f"{BASE}/me", headers=_hdrs(other_token),
            json={"slug": slug, "display_name": "New Owner"},
        )
    assert r.status_code == 201

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_delete_card_404_when_no_card(async_client, user):
    r = await async_client.delete(f"{BASE}/me", headers=_hdrs(user["token"]))
    assert r.status_code == 404


async def test_delete_card_no_auth_401(async_client):
    r = await async_client.delete(f"{BASE}/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /public/{slug}
# ---------------------------------------------------------------------------

async def test_get_public_card_200(async_client, user_with_card):
    r = await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")
    assert r.status_code == 200


async def test_get_public_card_no_auth_required(async_client, user_with_card):
    # No headers sent — must still return 200
    r = await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")
    assert r.status_code == 200


async def test_get_public_card_response_fields(async_client, user_with_card):
    r = await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")
    body = r.json()
    assert body["display_name"] == "Test User"
    assert body["title"] == "Engineer"
    assert "qr_code_url" in body


async def test_get_public_card_no_sensitive_fields(async_client, user_with_card):
    r = await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")
    body = r.json()
    # user_id must never be exposed on a public endpoint
    assert "user_id" not in body
    assert "id" not in body
    assert "view_count" not in body
    assert "is_public" not in body
    assert "created_at" not in body
    assert "updated_at" not in body


async def test_get_public_card_increments_view_count(async_client, user_with_card):
    slug = user_with_card["slug"]
    await async_client.get(f"{PUBLIC_BASE}/{slug}")
    await async_client.get(f"{PUBLIC_BASE}/{slug}")
    # view_count is visible via the authenticated /me endpoint
    r = await async_client.get(f"{BASE}/me", headers=_hdrs(user_with_card["token"]))
    assert r.json()["view_count"] >= 2


async def test_get_public_card_404_not_found(async_client):
    r = await async_client.get(f"{PUBLIC_BASE}/nonexistent-slug-xyz99")
    assert r.status_code == 404


async def test_get_public_card_private_returns_404(async_client, user_with_card):
    await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"is_public": False},
    )
    r = await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")
    assert r.status_code == 404


async def test_get_public_card_private_does_not_increment_view_count(async_client, user_with_card):
    db = get_database()
    # Make private
    await async_client.patch(
        f"{BASE}/me", headers=_hdrs(user_with_card["token"]),
        json={"is_public": False},
    )
    count_before = (await db["digital_cards"].find_one(
        {"slug": user_with_card["slug"]}, {"view_count": 1},
    ))["view_count"]

    await async_client.get(f"{PUBLIC_BASE}/{user_with_card['slug']}")

    count_after = (await db["digital_cards"].find_one(
        {"slug": user_with_card["slug"]}, {"view_count": 1},
    ))["view_count"]
    assert count_after == count_before
