"""
Test auto-tag generation: date · event · location
Khi tạo contact thì hệ thống tự động sinh tag, reuse nếu đã tồn tại.
"""
import uuid
from datetime import datetime

import pytest_asyncio

AUTH = "/api/v1/auth"
CONTACTS = "/api/v1/contacts"
EVENTS = "/api/v1/events"
TAGS = "/api/v1/tags"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tat_{s}",
        "email": f"tat_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "AutoTag Test",
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


# ---------------------------------------------------------------------------
# Date tag — "May 2026"
# ---------------------------------------------------------------------------

async def test_auto_date_tag_created(async_client, user):
    r = await async_client.post(CONTACTS + "/",
        json={"full_name": "Date Tag Test"},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201
    tag_ids = r.json()["tag_ids"]
    assert len(tag_ids) >= 1

    # Verify date tag exists in user's tag list
    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_names = [t["name"] for t in r2.json()["items"] if t["source"] == "auto"]
    expected = datetime.utcnow().strftime("%B %Y")
    assert expected in auto_names


async def test_auto_date_tag_reused_on_second_contact(async_client, user):
    await async_client.post(CONTACTS + "/",
        json={"full_name": "First Contact"},
        headers=_hdrs(user["token"]),
    )
    await async_client.post(CONTACTS + "/",
        json={"full_name": "Second Contact"},
        headers=_hdrs(user["token"]),
    )

    # Chỉ có 1 date tag dù tạo 2 contacts cùng tháng
    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    date_tags = [
        t for t in r.json()["items"]
        if t["source"] == "auto" and t["name"] == datetime.utcnow().strftime("%B %Y")
    ]
    assert len(date_tags) == 1


async def test_auto_date_tag_color_blue(async_client, user):
    await async_client.post(CONTACTS + "/",
        json={"full_name": "Color Test"},
        headers=_hdrs(user["token"]),
    )
    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    date_tag = next(
        (t for t in r.json()["items"]
         if t["source"] == "auto" and t["name"] == datetime.utcnow().strftime("%B %Y")),
        None,
    )
    assert date_tag is not None
    assert date_tag["color"] == "#60A0F0"


# ---------------------------------------------------------------------------
# Event tag — tên event
# ---------------------------------------------------------------------------

async def test_auto_event_tag_created(async_client, user):
    r_event = await async_client.post(EVENTS + "/",
        json={"name": "TechDay 2026", "location": "HCMC", "event_date": "2026-06-01T09:00:00"},
        headers=_hdrs(user["token"]),
    )
    assert r_event.status_code == 201
    event_id = r_event.json()["id"]

    r = await async_client.post(CONTACTS + "/",
        json={"full_name": "Event Contact", "event_id": event_id},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201

    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_names = [t["name"] for t in r2.json()["items"] if t["source"] == "auto"]
    assert "TechDay 2026" in auto_names


async def test_auto_event_tag_color_green(async_client, user):
    r_event = await async_client.post(EVENTS + "/",
        json={"name": "GreenEvent", "event_date": "2026-06-01T09:00:00"},
        headers=_hdrs(user["token"]),
    )
    event_id = r_event.json()["id"]

    await async_client.post(CONTACTS + "/",
        json={"full_name": "Green Contact", "event_id": event_id},
        headers=_hdrs(user["token"]),
    )

    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    event_tag = next(
        (t for t in r.json()["items"] if t["name"] == "GreenEvent"),
        None,
    )
    assert event_tag is not None
    assert event_tag["color"] == "#3DD68C"


async def test_no_event_tag_without_event_id(async_client, user):
    r = await async_client.post(CONTACTS + "/",
        json={"full_name": "No Event"},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201

    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_names = [t["name"] for t in r2.json()["items"] if t["source"] == "auto"]
    # chỉ có date tag, không có event tag
    assert len([n for n in auto_names if n not in [datetime.utcnow().strftime("%B %Y")]]) == 0


# ---------------------------------------------------------------------------
# Location tag — phần cuối của address
# ---------------------------------------------------------------------------

async def test_auto_location_tag_created(async_client, user):
    r = await async_client.post(CONTACTS + "/",
        json={"full_name": "Location Contact", "address": "123 Nguyen Hue, Ho Chi Minh City"},
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201

    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_names = [t["name"] for t in r2.json()["items"] if t["source"] == "auto"]
    assert "Ho Chi Minh City" in auto_names


async def test_auto_location_tag_color_amber(async_client, user):
    await async_client.post(CONTACTS + "/",
        json={"full_name": "Amber Contact", "address": "456 Hoan Kiem, Ha Noi"},
        headers=_hdrs(user["token"]),
    )

    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    loc_tag = next(
        (t for t in r.json()["items"] if t["name"] == "Ha Noi"),
        None,
    )
    assert loc_tag is not None
    assert loc_tag["color"] == "#F5A623"


async def test_no_location_tag_without_address(async_client, user):
    await async_client.post(CONTACTS + "/",
        json={"full_name": "No Address"},
        headers=_hdrs(user["token"]),
    )
    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_tags = [t for t in r.json()["items"] if t["source"] == "auto"]
    # Chỉ có date tag
    assert len(auto_tags) == 1


async def test_no_location_tag_single_segment_address(async_client, user):
    # Địa chỉ không có dấu phẩy → không tạo location tag (sẽ là cả chuỗi dài)
    await async_client.post(CONTACTS + "/",
        json={"full_name": "No Comma", "address": "X"},
        headers=_hdrs(user["token"]),
    )
    r = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_tags = [t for t in r.json()["items"] if t["source"] == "auto"]
    # "X" chỉ 1 ký tự → bị bỏ qua (min length 2), chỉ có date tag
    assert len(auto_tags) == 1


# ---------------------------------------------------------------------------
# All 3 tags cùng lúc
# ---------------------------------------------------------------------------

async def test_all_three_auto_tags(async_client, user):
    r_event = await async_client.post(EVENTS + "/",
        json={"name": "Startup Night", "event_date": "2026-06-01T09:00:00"},
        headers=_hdrs(user["token"]),
    )
    event_id = r_event.json()["id"]

    r = await async_client.post(CONTACTS + "/",
        json={
            "full_name": "Full Auto",
            "address": "789 Le Loi, Da Nang",
            "event_id": event_id,
        },
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201

    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    auto_names = [t["name"] for t in r2.json()["items"] if t["source"] == "auto"]

    assert datetime.utcnow().strftime("%B %Y") in auto_names  # date
    assert "Startup Night" in auto_names                       # event
    assert "Da Nang" in auto_names                             # location


async def test_auto_tags_assigned_to_contact(async_client, user):
    r_event = await async_client.post(EVENTS + "/",
        json={"name": "Demo Day", "event_date": "2026-06-01T09:00:00"},
        headers=_hdrs(user["token"]),
    )
    event_id = r_event.json()["id"]

    r = await async_client.post(CONTACTS + "/",
        json={
            "full_name": "Tagged Contact",
            "address": "1 Bach Dang, Hai Phong",
            "event_id": event_id,
        },
        headers=_hdrs(user["token"]),
    )
    assert r.status_code == 201
    contact_tag_ids = r.json()["tag_ids"]

    # tag_ids của contact phải chứa cả 3 auto tags
    r2 = await async_client.get(TAGS + "/", headers=_hdrs(user["token"]))
    all_tags = {t["id"]: t for t in r2.json()["items"]}

    auto_in_contact = [
        all_tags[tid]["name"]
        for tid in contact_tag_ids
        if tid in all_tags and all_tags[tid]["source"] == "auto"
    ]

    assert datetime.utcnow().strftime("%B %Y") in auto_in_contact
    assert "Demo Day" in auto_in_contact
    assert "Hai Phong" in auto_in_contact
