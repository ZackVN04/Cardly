import uuid

import pytest_asyncio

BASE = "/api/v1/tags"
AUTH = "/api/v1/auth"
CONTACTS = "/api/v1/contacts"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"ttag_{s}",
        "email": f"ttag_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Tag Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH}/signup", json=payload)
    assert r.status_code == 201

    r2 = await async_client.post(f"{AUTH}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {**payload, "token": token, "id": r.json()["id"]}

    await async_client.request(
        "DELETE", f"{AUTH}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


@pytest_asyncio.fixture
async def other_user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH}/signup", json=payload)
    assert r.status_code == 201

    r2 = await async_client.post(f"{AUTH}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]

    yield {**payload, "token": token, "id": r.json()["id"]}

    await async_client.request(
        "DELETE", f"{AUTH}/me",
        headers=_hdrs(token),
        json={"password": _PWD},
    )


# ---------------------------------------------------------------------------
# POST / — create tag
# ---------------------------------------------------------------------------

async def test_create_tag_201(async_client, user):
    r = await async_client.post(BASE + "/", json={"name": "VIP"}, headers=_hdrs(user["token"]))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "VIP"
    assert body["color"] == "#7F77DD"
    assert body["source"] == "manual"
    assert "id" in body
    assert body["owner_id"] == user["id"]


async def test_create_tag_custom_color(async_client, user):
    r = await async_client.post(BASE + "/",
        json={"name": "Investor", "color": "#FF0000"},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201
    assert r.json()["color"] == "#FF0000"


async def test_create_tag_no_auth_401(async_client):
    r = await async_client.post(BASE + "/", json={"name": "NoAuth"})
    assert r.status_code == 401


async def test_create_tag_invalid_color_422(async_client, user):
    r = await async_client.post(BASE + "/",
        json={"name": "Bad", "color": "red"},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 422


async def test_create_tag_empty_name_422(async_client, user):
    r = await async_client.post(BASE + "/",
        json={"name": ""},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 422


async def test_create_tag_name_too_long_422(async_client, user):
    r = await async_client.post(BASE + "/",
        json={"name": "x" * 51},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 422


async def test_create_tag_duplicate_name_409(async_client, user):
    await async_client.post(BASE + "/", json={"name": "Dup"}, headers=_hdrs(user["token"]))
    r = await async_client.post(BASE + "/", json={"name": "Dup"}, headers=_hdrs(user["token"]))
    assert r.status_code == 409


async def test_create_tag_duplicate_case_insensitive_409(async_client, user):
    await async_client.post(BASE + "/", json={"name": "Partner"}, headers=_hdrs(user["token"]))
    r = await async_client.post(BASE + "/", json={"name": "PARTNER"}, headers=_hdrs(user["token"]))
    assert r.status_code == 409


async def test_create_tag_same_name_different_user_ok(async_client, user, other_user):
    r1 = await async_client.post(BASE + "/", json={"name": "SharedName"}, headers=_hdrs(user["token"]))
    r2 = await async_client.post(BASE + "/", json={"name": "SharedName"}, headers=_hdrs(other_user["token"]))
    assert r1.status_code == 201
    assert r2.status_code == 201


# ---------------------------------------------------------------------------
# GET / — list tags
# ---------------------------------------------------------------------------

async def test_list_tags_empty(async_client, user):
    r = await async_client.get(BASE + "/", headers=_hdrs(user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_list_tags_returns_own_only(async_client, user, other_user):
    await async_client.post(BASE + "/", json={"name": "Mine"}, headers=_hdrs(user["token"]))
    await async_client.post(BASE + "/", json={"name": "Others"}, headers=_hdrs(other_user["token"]))

    r = await async_client.get(BASE + "/", headers=_hdrs(user["token"]))
    assert r.status_code == 200
    body = r.json()
    names = [t["name"] for t in body["items"]]
    assert "Mine" in names
    assert "Others" not in names


async def test_list_tags_pagination(async_client, user):
    for i in range(5):
        await async_client.post(BASE + "/", json={"name": f"Tag{i}"}, headers=_hdrs(user["token"]))

    r = await async_client.get(BASE + "/?limit=2&skip=0", headers=_hdrs(user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 5


async def test_list_tags_no_auth_401(async_client):
    r = await async_client.get(BASE + "/")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /{tag_id} — update tag
# ---------------------------------------------------------------------------

async def test_update_tag_name(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "Old"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"name": "New"}, headers=_hdrs(user["token"]))
    assert r2.status_code == 200
    assert r2.json()["name"] == "New"


async def test_update_tag_color(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "ColorTag"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"color": "#123456"}, headers=_hdrs(user["token"]))
    assert r2.status_code == 200
    assert r2.json()["color"] == "#123456"


async def test_update_tag_empty_body_returns_existing(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "Unchanged"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={}, headers=_hdrs(user["token"]))
    assert r2.status_code == 200
    assert r2.json()["name"] == "Unchanged"


async def test_update_tag_not_found_404(async_client, user):
    fake_id = "000000000000000000000001"
    r = await async_client.patch(f"{BASE}/{fake_id}", json={"name": "x"}, headers=_hdrs(user["token"]))
    assert r.status_code == 404


async def test_update_tag_wrong_owner_403(async_client, user, other_user):
    r1 = await async_client.post(BASE + "/", json={"name": "OwnedByUser"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"name": "Hijack"}, headers=_hdrs(other_user["token"]))
    assert r2.status_code == 403


async def test_update_tag_duplicate_name_409(async_client, user):
    await async_client.post(BASE + "/", json={"name": "Alpha"}, headers=_hdrs(user["token"]))
    r1 = await async_client.post(BASE + "/", json={"name": "Beta"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"name": "Alpha"}, headers=_hdrs(user["token"]))
    assert r2.status_code == 409


async def test_update_tag_same_name_no_conflict(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "SameName"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"name": "SameName"}, headers=_hdrs(user["token"]))
    assert r2.status_code == 200


async def test_update_tag_invalid_id_422(async_client, user):
    r = await async_client.patch(f"{BASE}/not-an-id", json={"name": "x"}, headers=_hdrs(user["token"]))
    assert r.status_code == 422


async def test_update_tag_invalid_color_422(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "ColorBad"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"color": "blue"}, headers=_hdrs(user["token"]))
    assert r2.status_code == 422


async def test_update_tag_no_auth_401(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "NoAuthPatch"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.patch(f"{BASE}/{tag_id}", json={"name": "x"})
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /{tag_id}
# ---------------------------------------------------------------------------

async def test_delete_tag_204(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "ToDelete"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.delete(f"{BASE}/{tag_id}", headers=_hdrs(user["token"]))
    assert r2.status_code == 204


async def test_delete_tag_removes_from_list(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "Gone"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    await async_client.delete(f"{BASE}/{tag_id}", headers=_hdrs(user["token"]))

    r2 = await async_client.get(BASE + "/", headers=_hdrs(user["token"]))
    names = [t["name"] for t in r2.json()["items"]]
    assert "Gone" not in names


async def test_delete_tag_not_found_404(async_client, user):
    fake_id = "000000000000000000000002"
    r = await async_client.delete(f"{BASE}/{fake_id}", headers=_hdrs(user["token"]))
    assert r.status_code == 404


async def test_delete_tag_wrong_owner_403(async_client, user, other_user):
    r1 = await async_client.post(BASE + "/", json={"name": "Protected"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.delete(f"{BASE}/{tag_id}", headers=_hdrs(other_user["token"]))
    assert r2.status_code == 403


async def test_delete_tag_invalid_id_422(async_client, user):
    r = await async_client.delete(f"{BASE}/bad-id", headers=_hdrs(user["token"]))
    assert r.status_code == 422


async def test_delete_tag_no_auth_401(async_client, user):
    r1 = await async_client.post(BASE + "/", json={"name": "NoAuthDel"}, headers=_hdrs(user["token"]))
    tag_id = r1.json()["id"]

    r2 = await async_client.delete(f"{BASE}/{tag_id}")
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# DELETE bulk pull — xóa tag phải gỡ khỏi contacts
# ---------------------------------------------------------------------------

async def test_delete_tag_removed_from_contact(async_client, user):
    r_tag = await async_client.post(BASE + "/", json={"name": "PullTest"}, headers=_hdrs(user["token"]))
    tag_id = r_tag.json()["id"]

    r_contact = await async_client.post(CONTACTS + "/",
        json={"full_name": "Test Contact", "tag_ids": [tag_id]},
        headers=_hdrs(user["token"]),
    )
    assert r_contact.status_code == 201
    contact_id = r_contact.json()["id"]

    await async_client.delete(f"{BASE}/{tag_id}", headers=_hdrs(user["token"]))

    r_get = await async_client.get(f"{CONTACTS}/{contact_id}", headers=_hdrs(user["token"]))
    assert r_get.status_code == 200
    assert tag_id not in r_get.json()["tag_ids"]
