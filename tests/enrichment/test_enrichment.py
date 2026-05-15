import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from bson import ObjectId

from src.core.rate_limit import limiter
from src.database import get_database

BASE = "/api/v1/enrichment"
AUTH_BASE = "/api/v1/auth"
CONTACTS_BASE = "/api/v1/contacts"
_PWD = "TestPass123"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tenrich_{s}",
        "email": f"tenrich_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Enrichment Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def enrich_user(async_client):
    payload = _new_user()
    r = await async_client.post(f"{AUTH_BASE}/signup", json=payload)
    assert r.status_code == 201
    r2 = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": payload["username"], "password": _PWD,
    })
    token = r2.json()["access_token"]
    yield {"token": token, "id": r.json()["id"], **payload}
    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me",
        headers=_hdrs(token), json={"password": _PWD},
    )


@pytest_asyncio.fixture
async def contact(async_client, enrich_user):
    r = await async_client.post(
        f"{CONTACTS_BASE}/",
        headers=_hdrs(enrich_user["token"]),
        json={"full_name": "Nguyen Van A", "company": "TechCorp", "email": "a@tech.com"},
    )
    assert r.status_code == 201
    yield r.json()


async def _insert_processing_enrichment(contact_id: ObjectId) -> None:
    db = get_database()
    await db["enrichment_results"].insert_one({
        "contact_id": contact_id,
        "status": "processing",
        "brief": None,
        "keywords": [],
        "highlights": [],
        "linkedin_data": None,
        "facebook_data": None,
        "website_data": None,
        "source": None,
        "enriched_at": datetime.utcnow(),
    })


async def _insert_completed_enrichment(
    contact_id: ObjectId,
    brief: str = "Old brief",
    keywords: list | None = None,
    highlights: list | None = None,
    linkedin_data: dict | None = None,
) -> None:
    db = get_database()
    await db["enrichment_results"].insert_one({
        "contact_id": contact_id,
        "status": "completed",
        "brief": brief,
        "keywords": keywords or ["old", "keywords"],
        "highlights": highlights or ["old highlight"],
        "linkedin_data": linkedin_data,
        "facebook_data": None,
        "website_data": None,
        "source": "gemini",
        "enriched_at": datetime.utcnow(),
    })


async def _insert_failed_enrichment(contact_id: ObjectId) -> None:
    db = get_database()
    await db["enrichment_results"].insert_one({
        "contact_id": contact_id,
        "status": "failed",
        "brief": None,
        "keywords": [],
        "highlights": [],
        "linkedin_data": None,
        "facebook_data": None,
        "website_data": None,
        "source": None,
        "enriched_at": datetime.utcnow(),
    })


# ---------------------------------------------------------------------------
# POST /{contact_id} — trigger
# ---------------------------------------------------------------------------

async def test_trigger_enrichment_202(async_client, enrich_user, contact):
    with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        )
    assert r.status_code == 202


async def test_trigger_enrichment_status_processing(async_client, enrich_user, contact):
    with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        )
    assert r.json()["status"] == "processing"


async def test_trigger_enrichment_409_already_running(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.post(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 409


async def test_trigger_enrichment_404_unknown_contact(async_client, enrich_user):
    r = await async_client.post(
        f"{BASE}/{ObjectId()}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 404


async def test_trigger_enrichment_403_not_owner(async_client, enrich_user, contact):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(other_token),
        )
    assert r.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_trigger_enrichment_no_auth(async_client, contact):
    r = await async_client.post(f"{BASE}/{contact['id']}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /{contact_id} — get result
# ---------------------------------------------------------------------------

async def test_get_enrichment_200(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.get(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 200
    assert r.json()["contact_id"] == contact["id"]


async def test_get_enrichment_404_not_triggered(async_client, enrich_user, contact):
    r = await async_client.get(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 404


async def test_get_enrichment_404_unknown_contact(async_client, enrich_user):
    r = await async_client.get(
        f"{BASE}/{ObjectId()}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 404


async def test_get_enrichment_no_auth(async_client, contact):
    r = await async_client.get(f"{BASE}/{contact['id']}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /{contact_id} — manual update
# ---------------------------------------------------------------------------

async def test_update_manual_200(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={"brief": "A seasoned tech professional.", "keywords": ["AI", "startup"]},
    )
    assert r.status_code == 200


async def test_update_manual_sets_source_manual(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={"brief": "Manual brief"},
    )
    assert r.json()["source"] == "manual"


async def test_update_manual_updates_fields(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={
            "brief": "Updated brief",
            "keywords": ["tech", "leadership"],
            "highlights": ["10 years experience"],
        },
    )
    body = r.json()
    assert body["brief"] == "Updated brief"
    assert "tech" in body["keywords"]
    assert "10 years experience" in body["highlights"]


async def test_update_manual_404_not_found(async_client, enrich_user, contact):
    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={"brief": "x"},
    )
    assert r.status_code == 404


async def test_update_manual_no_auth(async_client, contact):
    r = await async_client.patch(f"{BASE}/{contact['id']}", json={"brief": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /{contact_id}
# ---------------------------------------------------------------------------

async def test_delete_enrichment_204(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.delete(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 204


async def test_delete_enrichment_removes_from_db(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    await async_client.delete(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    r = await async_client.get(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 404


async def test_delete_enrichment_404_not_found(async_client, enrich_user, contact):
    r = await async_client.delete(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 404


async def test_delete_enrichment_no_auth(async_client, contact):
    r = await async_client.delete(f"{BASE}/{contact['id']}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET / — list all
# ---------------------------------------------------------------------------

async def test_list_enrichments_200(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))
    r = await async_client.get(f"{BASE}/", headers=_hdrs(enrich_user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1


async def test_list_enrichments_empty_for_new_user(async_client, enrich_user):
    r = await async_client.get(f"{BASE}/", headers=_hdrs(enrich_user["token"]))
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_list_enrichments_no_auth(async_client):
    r = await async_client.get(f"{BASE}/")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /{contact_id} — rate limit & edge cases
# ---------------------------------------------------------------------------

async def test_trigger_429_rate_limit(async_client, enrich_user, contact):
    # Dùng unique IP để tránh ô nhiễm counter từ các test khác
    unique_ip = f"10.{uuid.uuid4().hex[:3]}.0.1"
    original_key_func = limiter._key_func
    limiter._key_func = lambda _req: unique_ip

    try:
        # 5 request đầu đều hợp lệ về mặt rate limit
        # (request 1 → 202, request 2-5 → 409 vì đang processing — nhưng đều tính vào counter)
        for _ in range(5):
            with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
                await async_client.post(
                    f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
                )
        # Request thứ 6 → 429 Too Many Requests
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        )
        assert r.status_code == 429
    finally:
        limiter._key_func = original_key_func


async def test_trigger_invalid_contact_id_422(async_client, enrich_user):
    # ObjectId không hợp lệ → router parse_object_id raise 422 ngay lập tức
    r = await async_client.post(
        f"{BASE}/not-a-valid-objectid", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Re-run flow — archive activity log
# ---------------------------------------------------------------------------

async def test_trigger_rerun_archives_completed_to_activity_log(async_client, enrich_user, contact):
    db = get_database()
    contact_oid = ObjectId(contact["id"])

    # Bước 1: Insert enrichment đã completed với dữ liệu cụ thể
    await _insert_completed_enrichment(
        contact_oid,
        brief="Archived brief",
        keywords=["archived", "keyword"],
        linkedin_data={"connections": 200, "current_role": "CTO"},
    )

    # Bước 2: Trigger lại (re-run) — mock để không gọi Gemini thật
    with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        )
    assert r.status_code == 202
    assert r.json()["status"] == "processing"  # đã reset về processing

    # Bước 3: Kiểm tra activity_log có bản ghi archive với previous_values đúng
    logs = await db["contact_activity_logs"].find({
        "contact_id": contact_oid,
        "action": "enriched",
        "source": "enrichment",
    }).to_list(length=10)

    assert len(logs) >= 1
    archive = logs[0]
    assert archive["previous_values"]["brief"] == "Archived brief"
    assert archive["previous_values"]["keywords"] == ["archived", "keyword"]
    assert archive["previous_values"]["linkedin_data"] == {"connections": 200, "current_role": "CTO"}
    # new_values phải là trống (reset)
    assert archive["new_values"]["brief"] is None
    assert archive["new_values"]["keywords"] == []


async def test_trigger_rerun_failed_does_not_archive(async_client, enrich_user, contact):
    db = get_database()
    contact_oid = ObjectId(contact["id"])

    # Enrichment failed → không có gì để archive
    await _insert_failed_enrichment(contact_oid)

    with patch("src.enrichment.service._run_enrichment_async", AsyncMock(return_value=None)):
        r = await async_client.post(
            f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        )
    assert r.status_code == 202

    # Không được có bản ghi archive nào
    count = await db["contact_activity_logs"].count_documents({
        "contact_id": contact_oid,
        "action": "enriched",
        "source": "enrichment",
    })
    assert count == 0


# ---------------------------------------------------------------------------
# GET /{contact_id} — 403 not owner
# ---------------------------------------------------------------------------

async def test_get_enrichment_403_not_owner(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r = await async_client.get(
        f"{BASE}/{contact['id']}", headers=_hdrs(other_token),
    )
    assert r.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


# ---------------------------------------------------------------------------
# GET / — filter status, isolation, pagination
# ---------------------------------------------------------------------------

async def test_list_enrichments_filter_status_processing(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    r = await async_client.get(
        f"{BASE}/?status=processing", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(item["status"] == "processing" for item in body["items"])


async def test_list_enrichments_filter_status_completed_returns_empty(async_client, enrich_user, contact):
    # Chỉ có processing, filter completed → 0 kết quả
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    r = await async_client.get(
        f"{BASE}/?status=completed", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_list_enrichments_isolation(async_client, enrich_user, contact):
    # User A có enrichment → User B không được thấy
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r = await async_client.get(f"{BASE}/", headers=_hdrs(other_token))
    assert r.json()["total"] == 0  # user B thấy rỗng

    r2 = await async_client.get(f"{BASE}/", headers=_hdrs(enrich_user["token"]))
    assert r2.json()["total"] >= 1  # user A thấy của mình

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_list_enrichments_pagination(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    r = await async_client.get(
        f"{BASE}/?skip=0&limit=1", headers=_hdrs(enrich_user["token"]),
    )
    body = r.json()
    assert r.status_code == 200
    assert len(body["items"]) <= 1
    assert body["limit"] == 1
    assert body["skip"] == 0


# ---------------------------------------------------------------------------
# PATCH /{contact_id} — 403, social data, activity log changed_fields
# ---------------------------------------------------------------------------

async def test_update_manual_403_not_owner(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(other_token),
        json={"brief": "injected"},
    )
    assert r.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_update_manual_social_data_fields(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={
            "linkedin_data": {"connections": 500, "current_role": "CEO at TechCorp"},
            "facebook_data": {"profile_url": "fb.com/test", "followers": 1200, "recent_posts": []},
            "website_data": {"about": "AI startup", "founded": "2020", "team_size": "50+"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["linkedin_data"]["connections"] == 500
    assert body["facebook_data"]["followers"] == 1200
    assert body["website_data"]["founded"] == "2020"
    assert body["source"] == "manual"


async def test_update_manual_tracks_changed_fields_in_activity_log(async_client, enrich_user, contact):
    db = get_database()
    contact_oid = ObjectId(contact["id"])

    await _insert_completed_enrichment(contact_oid, brief="Before patch")

    r = await async_client.patch(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
        json={"brief": "After patch", "keywords": ["updated"]},
    )
    assert r.status_code == 200

    log = await db["contact_activity_logs"].find_one({
        "contact_id": contact_oid,
        "action": "enriched",
        "source": "manual",
    })
    assert log is not None
    # Chỉ các field được gửi mới xuất hiện trong changed_fields
    assert "brief" in log["changed_fields"]
    assert "keywords" in log["changed_fields"]
    assert "highlights" not in log["changed_fields"]  # không gửi → không track
    # Giá trị trước và sau đúng
    assert log["previous_values"]["brief"] == "Before patch"
    assert log["new_values"]["brief"] == "After patch"
    assert log["new_values"]["keywords"] == ["updated"]


# ---------------------------------------------------------------------------
# DELETE /{contact_id} — 403, activity log snapshot đầy đủ
# ---------------------------------------------------------------------------

async def test_delete_enrichment_403_not_owner(async_client, enrich_user, contact):
    await _insert_processing_enrichment(ObjectId(contact["id"]))

    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r = await async_client.delete(
        f"{BASE}/{contact['id']}", headers=_hdrs(other_token),
    )
    assert r.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_delete_logs_full_snapshot_to_activity_log(async_client, enrich_user, contact):
    db = get_database()
    contact_oid = ObjectId(contact["id"])

    await _insert_completed_enrichment(
        contact_oid,
        brief="To be deleted",
        keywords=["del", "ete"],
        highlights=["highlight before delete"],
    )

    r = await async_client.delete(
        f"{BASE}/{contact['id']}", headers=_hdrs(enrich_user["token"]),
    )
    assert r.status_code == 204

    log = await db["contact_activity_logs"].find_one({
        "contact_id": contact_oid,
        "action": "enriched",
        "source": "user_edit",
    })
    assert log is not None
    # previous_values phải là snapshot đầy đủ trước khi xóa
    assert log["previous_values"]["brief"] == "To be deleted"
    assert log["previous_values"]["keywords"] == ["del", "ete"]
    assert log["previous_values"]["highlights"] == ["highlight before delete"]
    # new_values phải là tất cả null/empty theo API spec
    assert log["new_values"]["brief"] is None
    assert log["new_values"]["keywords"] == []
    assert log["new_values"]["highlights"] == []
    assert log["new_values"]["linkedin_data"] is None
