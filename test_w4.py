"""
Test W4: tags, events, activity
Run: python test_w4.py  (server must be running at http://127.0.0.1:8000)
Auth endpoint not yet implemented -> script generates JWT token directly from .env secret.
"""

import sys

import httpx
from bson import ObjectId
from dotenv import dotenv_values

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

config = dotenv_values(".env")
JWT_SECRET = config.get("JWT_SECRET") or config.get("jwt_secret")
if not JWT_SECRET:
    print("[FAIL] JWT_SECRET not found in .env")
    sys.exit(1)

BASE = "http://127.0.0.1:8000/api/v1"
FAKE_USER_ID = str(ObjectId())


def make_token() -> str:
    from src.auth.utils import create_jwt
    from src.auth.constants import ACCESS_TOKEN_EXPIRE
    return create_jwt({"sub": FAKE_USER_ID}, ACCESS_TOKEN_EXPIRE, JWT_SECRET)


TOKEN = make_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

PASS = 0
FAIL = 0


def check(label: str, resp: httpx.Response, expected: int):
    global PASS, FAIL
    ok = resp.status_code == expected
    mark = "OK" if ok else "!!"
    status = "PASS" if ok else f"FAIL (got {resp.status_code})"
    print(f"  [{mark}] {label}: {status}")
    if not ok:
        FAIL += 1
        try:
            print(f"      {resp.json()}")
        except Exception:
            print(f"      {resp.text[:200]}")
    else:
        PASS += 1
    return resp


# ==========================================================================
# TAGS
# ==========================================================================

print("\n--- TAGS ---")

with httpx.Client(headers=HEADERS, timeout=10) as c:

    # POST / - create tag
    r = check("POST /tags/", c.post(f"{BASE}/tags/", json={
        "name": "test-tag-w4",
        "color": "#FF5733",
        "source": "manual",
    }), 201)
    tag_id = r.json().get("id") if r.status_code == 201 else None

    # POST / - duplicate name -> 409
    check("POST /tags/ duplicate name (expect 409)", c.post(f"{BASE}/tags/", json={
        "name": "test-tag-w4",
        "color": "#AABBCC",
    }), 409)

    # POST / - second tag
    r2 = check("POST /tags/ second tag", c.post(f"{BASE}/tags/", json={
        "name": "test-tag-w4-second",
        "color": "#7F77DD",
    }), 201)
    tag_id2 = r2.json().get("id") if r2.status_code == 201 else None

    # GET / - list
    r = check("GET /tags/", c.get(f"{BASE}/tags/"), 200)
    if r.status_code == 200:
        body = r.json()
        print(f"      total={body.get('total')}  items={len(body.get('items', []))}")

    if tag_id:
        # PATCH /{id} - rename
        check("PATCH /tags/{id}", c.patch(f"{BASE}/tags/{tag_id}", json={
            "name": "test-tag-w4-updated",
        }), 200)

        # PATCH /{id} - conflict name -> 409
        if tag_id2:
            check("PATCH /tags/{id} conflict name (expect 409)", c.patch(f"{BASE}/tags/{tag_id}", json={
                "name": "test-tag-w4-second",
            }), 409)

        # PATCH bad id -> 422
        check("PATCH /tags/bad-id (expect 422)", c.patch(f"{BASE}/tags/notanobjectid", json={
            "name": "x",
        }), 422)

        # DELETE /{id}
        check("DELETE /tags/{id}", c.delete(f"{BASE}/tags/{tag_id}"), 204)

        # DELETE already deleted -> 404
        check("DELETE /tags/{id} already deleted (expect 404)", c.delete(f"{BASE}/tags/{tag_id}"), 404)

    # Cleanup tag2
    if tag_id2:
        c.delete(f"{BASE}/tags/{tag_id2}")


# ==========================================================================
# EVENTS
# ==========================================================================

print("\n--- EVENTS ---")

with httpx.Client(headers=HEADERS, timeout=10) as c:

    # POST / - create event
    r = check("POST /events/", c.post(f"{BASE}/events/", json={
        "name": "TechDay W4 Test",
        "location": "Ho Chi Minh City",
        "event_date": "2026-06-15T09:00:00",
        "description": "Test event for W4",
    }), 201)
    event_id = r.json().get("id") if r.status_code == 201 else None

    # POST / - second event
    r2 = check("POST /events/ second", c.post(f"{BASE}/events/", json={
        "name": "Startup Summit",
        "event_date": "2026-07-01T08:00:00",
    }), 201)
    event_id2 = r2.json().get("id") if r2.status_code == 201 else None

    # GET / - list
    r = check("GET /events/", c.get(f"{BASE}/events/"), 200)
    if r.status_code == 200:
        body = r.json()
        print(f"      total={body.get('total')}  items={len(body.get('items', []))}")

    if event_id:
        # GET /{id} - with contacts via $lookup
        r = check("GET /events/{id} with contacts", c.get(f"{BASE}/events/{event_id}"), 200)
        if r.status_code == 200:
            body = r.json()
            print(f"      contacts_total={body.get('contacts_total')}  contacts={len(body.get('contacts', []))}")

        # PATCH /{id}
        check("PATCH /events/{id}", c.patch(f"{BASE}/events/{event_id}", json={
            "name": "TechDay W4 Updated",
            "location": "Ha Noi",
        }), 200)

        # PATCH empty body -> 200 (no DB write)
        check("PATCH /events/{id} empty body (expect 200)", c.patch(f"{BASE}/events/{event_id}", json={}), 200)

        # GET bad id -> 422
        check("GET /events/bad-id (expect 422)", c.get(f"{BASE}/events/notanobjectid"), 422)

        # DELETE /{id}
        check("DELETE /events/{id}", c.delete(f"{BASE}/events/{event_id}"), 204)

        # DELETE already deleted -> 404
        check("DELETE /events/{id} already deleted (expect 404)", c.delete(f"{BASE}/events/{event_id}"), 404)

    # Cleanup
    if event_id2:
        c.delete(f"{BASE}/events/{event_id2}")


# ==========================================================================
# ACTIVITY
# ==========================================================================

print("\n--- ACTIVITY ---")

with httpx.Client(headers=HEADERS, timeout=10) as c:

    # GET / - all logs
    r = check("GET /activity/", c.get(f"{BASE}/activity/"), 200)
    if r.status_code == 200:
        body = r.json()
        print(f"      total={body.get('total')}  items={len(body.get('items', []))}")

    # GET / filter by action=created
    r = check("GET /activity/?action=created", c.get(f"{BASE}/activity/", params={"action": "created"}), 200)
    if r.status_code == 200:
        print(f"      total={r.json().get('total')}")

    # GET / filter by action=deleted
    check("GET /activity/?action=deleted", c.get(f"{BASE}/activity/", params={"action": "deleted"}), 200)

    # GET /contacts/{contact_id} - fake id -> total=0
    fake_contact_id = str(ObjectId())
    r = check("GET /activity/contacts/{id} no logs (expect total=0)", c.get(f"{BASE}/activity/contacts/{fake_contact_id}"), 200)
    if r.status_code == 200:
        print(f"      total={r.json().get('total')}")

    # GET /contacts/bad-id -> 422
    check("GET /activity/contacts/bad-id (expect 422)", c.get(f"{BASE}/activity/contacts/notanid"), 422)


# ==========================================================================
# SUMMARY
# ==========================================================================

total = PASS + FAIL
result = "ALL PASS" if FAIL == 0 else f"{FAIL} FAILED"
print(f"\n== RESULT: {PASS}/{total} PASS  [{result}]")
