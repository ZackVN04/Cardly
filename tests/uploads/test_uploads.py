import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from bson import ObjectId
from src.database import get_database

BASE = "/api/v1/uploads"
AUTH_BASE = "/api/v1/auth"
_PWD = "TestPass123"
_FAKE_URL = "https://storage.googleapis.com/fake-bucket/avatars/test.jpg"


def _new_user():
    s = uuid.uuid4().hex[:8]
    return {
        "username": f"tupload_{s}",
        "email": f"tupload_{s}@cardly.dev",
        "password": _PWD,
        "full_name": "Upload Test User",
    }


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _jpeg_file(size: int = 1024, filename: str = "avatar.jpg"):
    return ("file", (filename, io.BytesIO(b"x" * size), "image/jpeg"))


@pytest_asyncio.fixture
async def upload_user(async_client):
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


@pytest.fixture
def mock_gcs():
    mock_upload = AsyncMock(return_value=_FAKE_URL)
    mock_delete = AsyncMock(return_value=None)
    with patch("src.uploads.service.upload_to_gcs", mock_upload), \
         patch("src.uploads.service.delete_from_gcs", mock_delete):
        yield {"upload": mock_upload, "delete": mock_delete}


async def test_upload_avatar_201(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    assert r.status_code == 201


async def test_upload_avatar_response_has_url(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    assert r.json()["url"] == _FAKE_URL


async def test_upload_avatar_response_has_blob_name(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    assert "blob_name" in r.json()


async def test_upload_avatar_response_has_uploaded_at(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    assert "uploaded_at" in r.json()


async def test_upload_avatar_updates_avatar_url_in_db(async_client, upload_user, mock_gcs):
    await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    db = get_database()
    doc = await db["users"].find_one({"_id": ObjectId(upload_user["id"])})
    assert doc["avatar_url"] == _FAKE_URL


async def test_upload_avatar_updates_blob_name_in_db(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    db = get_database()
    doc = await db["users"].find_one({"_id": ObjectId(upload_user["id"])})
    assert doc["avatar_blob_name"] == r.json()["blob_name"]


async def test_upload_avatar_png(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[("file", ("avatar.png", io.BytesIO(b"x" * 1024), "image/png"))],
    )
    assert r.status_code == 201


async def test_upload_avatar_webp(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[("file", ("avatar.webp", io.BytesIO(b"x" * 1024), "image/webp"))],
    )
    assert r.status_code == 201


async def test_upload_avatar_wrong_mime(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[("file", ("avatar.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert r.status_code == 415


async def test_upload_avatar_wrong_extension(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[("file", ("avatar.gif", io.BytesIO(b"x" * 1024), "image/jpeg"))],
    )
    assert r.status_code == 415


async def test_upload_avatar_too_large(async_client, upload_user, mock_gcs):
    big = 5 * 1024 * 1024 + 1
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file(size=big)],
    )
    assert r.status_code == 413


async def test_upload_avatar_exactly_at_limit(async_client, upload_user, mock_gcs):
    exact = 5 * 1024 * 1024
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file(size=exact)],
    )
    assert r.status_code == 201


async def test_upload_avatar_one_byte_over_limit(async_client, upload_user, mock_gcs):
    over = 5 * 1024 * 1024 + 1
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file(size=over)],
    )
    assert r.status_code == 413


async def test_upload_avatar_no_auth(async_client, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        files=[_jpeg_file()],
    )
    assert r.status_code == 401


async def test_upload_avatar_invalid_token(async_client, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs("invalid.token.value"),
        files=[_jpeg_file()],
    )
    assert r.status_code == 401


async def test_upload_avatar_no_file(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
    )
    assert r.status_code == 422


async def test_upload_avatar_deletes_old_blob(async_client, upload_user, mock_gcs):
    old_blob = "avatars/old_avatar_blob.jpg"
    db = get_database()
    await db["users"].update_one(
        {"_id": ObjectId(upload_user["id"])},
        {"$set": {"avatar_blob_name": old_blob}},
    )

    await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )

    mock_gcs["delete"].assert_called_once_with(old_blob)


async def test_upload_avatar_no_delete_on_first_upload(async_client, upload_user, mock_gcs):
    db = get_database()
    await db["users"].update_one(
        {"_id": ObjectId(upload_user["id"])},
        {"$unset": {"avatar_blob_name": ""}},
    )

    await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )

    mock_gcs["delete"].assert_not_called()


async def test_upload_avatar_blob_name_starts_with_avatars(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    assert r.json()["blob_name"].startswith("avatars/")


async def test_upload_avatar_url_is_string(async_client, upload_user, mock_gcs):
    r = await async_client.post(
        f"{BASE}/avatar",
        headers=_hdrs(upload_user["token"]),
        files=[_jpeg_file()],
    )
    url = r.json()["url"]
    assert isinstance(url, str) and len(url) > 0
