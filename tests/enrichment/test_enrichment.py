import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from bson import ObjectId

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
    """Insert an in-progress enrichment doc directly to test 409."""
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
