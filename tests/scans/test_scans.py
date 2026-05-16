import io
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from bson import ObjectId

from src.database import get_database

BASE = "/api/v1/scans"
AUTH_BASE = "/api/v1/auth"
TAGS_BASE = "/api/v1/tags"
_PWD = "TestPass123"
_FAKE_URL = "https://storage.googleapis.com/fake-bucket/scans/test.jpg"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tscan_{s}",
        "email": f"tscan_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Scan Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _jpeg(size: int = 1024, name: str = "card.jpg"):
    return ("file", (name, io.BytesIO(b"\xff\xd8" + b"x" * size), "image/jpeg"))


@pytest_asyncio.fixture
async def scan_user(async_client):
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


@pytest.fixture
def mock_gcs():
    with patch("src.scans.router.upload_to_gcs", AsyncMock(return_value=_FAKE_URL)), \
        patch("src.scans.ocr_client.run_ocr", AsyncMock(return_value=None)):
        yield


async def _make_completed_scan(owner_id: ObjectId) -> str:
    db = get_database()
    doc = {
        "owner_id": owner_id,
        "event_id": None,
        "image_url": _FAKE_URL,
        "status": "completed",
        "raw_text": "Nguyen Van A\nCEO\nTechCorp",
        "extracted_data": {
            "full_name": "Nguyen Van A",
            "position": "CEO",
            "company": "TechCorp",
            "phone": "0901234567",
            "email": "a@techcorp.com",
        },
        "confidence_score": 0.86,
        "scanned_at": datetime.utcnow(),
    }
    result = await db["business_card_scans"].insert_one(doc)
    return str(result.inserted_id)


# ---------------------------------------------------------------------------
# POST / — upload
# ---------------------------------------------------------------------------

async def test_upload_scan_202(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()],
    )
    assert r.status_code == 202


async def test_upload_scan_status_processing(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()],
    )
    assert r.json()["status"] == "processing"


async def test_upload_scan_response_has_id(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()],
    )
    assert "id" in r.json()


async def test_upload_scan_wrong_mime(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]),
        files=[("file", ("card.pdf", io.BytesIO(b"x"), "application/pdf"))],
    )
    assert r.status_code == 415


async def test_upload_scan_wrong_extension(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]),
        files=[("file", ("card.gif", io.BytesIO(b"x" * 1024), "image/jpeg"))],
    )
    assert r.status_code == 415


async def test_upload_scan_too_large(async_client, scan_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/", headers=_hdrs(scan_user["token"]),
        files=[_jpeg(size=5 * 1024 * 1024 + 1)],
    )
    assert r.status_code == 413


async def test_upload_scan_no_auth(async_client, mock_gcs):
    r = await async_client.post(f"{BASE}/", files=[_jpeg()])
    assert r.status_code == 401


async def test_upload_scan_no_file(async_client, scan_user):
    r = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET / — list
# ---------------------------------------------------------------------------

async def test_list_scans_200(async_client, scan_user, mock_gcs):
    await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    r = await async_client.get(f"{BASE}/", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1


async def test_list_scans_filter_by_status(async_client, scan_user, mock_gcs):
    await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    r = await async_client.get(f"{BASE}/?status=processing", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "processing"


async def test_list_scans_no_auth(async_client):
    r = await async_client.get(f"{BASE}/")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /{scan_id} — get
# ---------------------------------------------------------------------------

async def test_get_scan_200(async_client, scan_user, mock_gcs):
    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    r2 = await async_client.get(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    assert r2.status_code == 200
    assert r2.json()["id"] == scan_id


async def test_get_scan_not_found(async_client, scan_user):
    r = await async_client.get(f"{BASE}/{ObjectId()}", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 404


async def test_get_scan_wrong_owner(async_client, scan_user, mock_gcs):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    r2 = await async_client.get(f"{BASE}/{scan_id}", headers=_hdrs(other_token))
    assert r2.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


# ---------------------------------------------------------------------------
# PATCH /{scan_id}
# ---------------------------------------------------------------------------

async def test_patch_scan_raw_text(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.patch(
        f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]),
        json={"raw_text": "Tran Thi B, CEO, TechCorp"},
    )
    assert r.status_code == 200
    assert r.json()["raw_text"] == "Tran Thi B, CEO, TechCorp"


async def test_patch_scan_extracted_data_merges(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.patch(
        f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]),
        json={"extracted_data": {"full_name": "Le Van C", "company": "StartupABC"}},
    )
    assert r.status_code == 200
    ed = r.json()["extracted_data"]
    assert ed["full_name"] == "Le Van C"
    assert ed["company"] == "StartupABC"


async def test_patch_confirmed_scan_blocked(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]),
        json={"confirmed_data": {"full_name": "Nguyen Van A"}},
    )
    r = await async_client.patch(
        f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]),
        json={"raw_text": "should be blocked"},
    )
    assert r.status_code == 400


async def test_patch_scan_no_auth(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.patch(f"{BASE}/{scan_id}", json={"raw_text": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /{scan_id}/confirm
# ---------------------------------------------------------------------------

async def test_confirm_scan_creates_contact(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]),
        json={"confirmed_data": {"full_name": "Nguyen Van A", "company": "TechCorp"}},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["full_name"] == "Nguyen Van A"
    assert body["scan_id"] == scan_id


async def test_confirm_scan_scan_id_linked(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]),
        json={"confirmed_data": {"full_name": "Nguyen Van A"}},
    )
    assert r.json()["scan_id"] == scan_id


async def test_confirm_scan_already_confirmed(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    payload = {"confirmed_data": {"full_name": "Nguyen Van A"}}
    await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]), json=payload,
    )
    r2 = await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]), json=payload,
    )
    assert r2.status_code == 409


async def test_confirm_scan_requires_completed_status(async_client, scan_user, mock_gcs):
    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    r2 = await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]),
        json={"confirmed_data": {"full_name": "Nguyen Van A"}},
    )
    assert r2.status_code == 400


async def test_confirm_scan_foreign_tag_403(async_client, scan_user):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]
    r_tag = await async_client.post(
        f"{TAGS_BASE}/", headers=_hdrs(other_token),
        json={"name": "ForeignTag", "color": "#FF0000"},
    )
    foreign_tag_id = r_tag.json()["id"]

    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.post(
        f"{BASE}/{scan_id}/confirm", headers=_hdrs(scan_user["token"]),
        json={"confirmed_data": {"full_name": "Nguyen Van A"}, "tag_ids": [foreign_tag_id]},
    )
    assert r.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_confirm_scan_no_auth(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.post(
        f"{BASE}/{scan_id}/confirm",
        json={"confirmed_data": {"full_name": "Nguyen Van A"}},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /{scan_id}
# ---------------------------------------------------------------------------

async def test_delete_scan_204(async_client, scan_user, mock_gcs):
    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    r2 = await async_client.delete(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    assert r2.status_code == 204


async def test_delete_scan_removes_from_db(async_client, scan_user, mock_gcs):
    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    await async_client.delete(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    r2 = await async_client.get(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    assert r2.status_code == 404


async def test_delete_scan_not_found(async_client, scan_user):
    r = await async_client.delete(f"{BASE}/{ObjectId()}", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 404


async def test_delete_scan_wrong_owner(async_client, scan_user, mock_gcs):
    other = _new_user()
    await async_client.post(f"{AUTH_BASE}/signup", json=other)
    r_s = await async_client.post(f"{AUTH_BASE}/signin", json={
        "username": other["username"], "password": _PWD,
    })
    other_token = r_s.json()["access_token"]

    r1 = await async_client.post(f"{BASE}/", headers=_hdrs(scan_user["token"]), files=[_jpeg()])
    scan_id = r1.json()["id"]
    r2 = await async_client.delete(f"{BASE}/{scan_id}", headers=_hdrs(other_token))
    assert r2.status_code == 403

    await async_client.request(
        "DELETE", f"{AUTH_BASE}/me", headers=_hdrs(other_token), json={"password": _PWD},
    )


async def test_delete_scan_no_auth(async_client, scan_user):
    scan_id = await _make_completed_scan(ObjectId(scan_user["id"]))
    r = await async_client.delete(f"{BASE}/{scan_id}")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# OCR error handling — timeout, failed status, retry
# ---------------------------------------------------------------------------

async def test_get_scan_failed_returns_422(async_client, scan_user):
    """GET /{id} trả 422 khi OCR thất bại — client phải dừng poll."""
    db = get_database()
    doc = {
        "owner_id": ObjectId(scan_user["id"]),
        "event_id": None,
        "image_url": _FAKE_URL,
        "status": "failed",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow(),
    }
    result = await db["business_card_scans"].insert_one(doc)
    scan_id = str(result.inserted_id)

    r = await async_client.get(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 422

    await db["business_card_scans"].delete_one({"_id": result.inserted_id})


async def test_get_scan_processing_timeout_returns_408(async_client, scan_user):
    """GET /{id} trả 408 khi scan vẫn processing sau hơn 30 giây."""
    db = get_database()
    doc = {
        "owner_id": ObjectId(scan_user["id"]),
        "event_id": None,
        "image_url": _FAKE_URL,
        "status": "processing",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow() - timedelta(seconds=60),
    }
    result = await db["business_card_scans"].insert_one(doc)
    scan_id = str(result.inserted_id)

    r = await async_client.get(f"{BASE}/{scan_id}", headers=_hdrs(scan_user["token"]))
    assert r.status_code == 408

    await db["business_card_scans"].delete_one({"_id": result.inserted_id})


async def test_ocr_retries_on_transient_gemini_error(async_client, scan_user):
    """run_ocr retry tối đa 3 lần khi Gemini trả 503; scan thành công ở lần 3."""
    from src.scans import ocr_client

    db = get_database()
    doc = {
        "owner_id": ObjectId(scan_user["id"]),
        "image_url": _FAKE_URL,
        "status": "processing",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow(),
    }
    result = await db["business_card_scans"].insert_one(doc)
    scan_id = result.inserted_id

    call_count = 0

    async def flaky_gemini(image_bytes: bytes, mime_type: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            raise httpx.HTTPStatusError("503", request=MagicMock(), response=mock_resp)
        return '{"full_name": "Retry User", "position": "CTO", "company": "RetryTest"}'

    with patch("src.scans.ocr_client._fetch_image", AsyncMock(return_value=(b"img", "image/jpeg"))), \
         patch("src.scans.ocr_client._call_gemini", side_effect=flaky_gemini), \
         patch("src.scans.ocr_client.asyncio.sleep", AsyncMock()):
        await ocr_client.run_ocr(db, scan_id, _FAKE_URL)

    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    assert scan["status"] == "completed"
    assert call_count == 3
    assert scan["extracted_data"]["full_name"] == "Retry User"

    await db["business_card_scans"].delete_one({"_id": scan_id})


async def test_ocr_marks_failed_when_all_retries_exhausted(async_client, scan_user):
    """run_ocr mark scan='failed' khi Gemini lỗi cả 3 lần."""
    from src.scans import ocr_client

    db = get_database()
    doc = {
        "owner_id": ObjectId(scan_user["id"]),
        "image_url": _FAKE_URL,
        "status": "processing",
        "raw_text": None,
        "extracted_data": None,
        "confidence_score": None,
        "scanned_at": datetime.utcnow(),
    }
    result = await db["business_card_scans"].insert_one(doc)
    scan_id = result.inserted_id

    async def always_503(image_bytes: bytes, mime_type: str) -> str:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=mock_resp)

    with patch("src.scans.ocr_client._fetch_image", AsyncMock(return_value=(b"img", "image/jpeg"))), \
         patch("src.scans.ocr_client._call_gemini", side_effect=always_503), \
         patch("src.scans.ocr_client.asyncio.sleep", AsyncMock()):
        await ocr_client.run_ocr(db, scan_id, _FAKE_URL)

    scan = await db["business_card_scans"].find_one({"_id": scan_id})
    assert scan["status"] == "failed"

    await db["business_card_scans"].delete_one({"_id": scan_id})
