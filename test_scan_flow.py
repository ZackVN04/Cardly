"""
Test luồng scan hoàn chỉnh: signup → signin → upload → poll → confirm → enrich → card → public
"""
import asyncio
import time
import httpx

BASE = "http://localhost:8000/api/v1"
IMAGE_PATH = "test_card.jpg"

USER = {
    "username": "scanflow_test",
    "email": "scanflow@cardly.dev",
    "password": "TestPass123",
    "full_name": "Scan Flow Tester",
}


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def run():
    async with httpx.AsyncClient(timeout=60.0) as c:

        # ── 1. Signup ──────────────────────────────────────────────────────
        print("\n[1] SIGNUP")
        r = await c.post(f"{BASE}/auth/signup", json=USER)
        if r.status_code == 409:
            print("   User already exists, skipping signup")
        else:
            assert r.status_code == 201, f"Signup failed: {r.text}"
            print(f"   OK Created user id={r.json()['id']}")

        # ── 2. Signin ──────────────────────────────────────────────────────
        print("\n[2] SIGNIN")
        r = await c.post(f"{BASE}/auth/signin", json={
            "username": USER["username"], "password": USER["password"],
        })
        assert r.status_code == 200, f"Signin failed: {r.text}"
        token = r.json()["access_token"]
        print(f"   OK token={token[:40]}...")

        # ── 3. Upload scan ─────────────────────────────────────────────────
        print("\n[3] UPLOAD SCAN")
        with open(IMAGE_PATH, "rb") as f:
            r = await c.post(
                f"{BASE}/scans/",
                headers=hdr(token),
                files={"file": ("test_card.jpg", f, "image/jpeg")},
            )
        assert r.status_code == 202, f"Upload failed: {r.text}"
        scan = r.json()
        scan_id = scan["id"]
        print(f"   OK scan_id={scan_id}  status={scan['status']}")

        # ── 4. Poll đến completed ──────────────────────────────────────────
        print("\n[4] POLL OCR")
        for attempt in range(20):
            await asyncio.sleep(3)
            r = await c.get(f"{BASE}/scans/{scan_id}", headers=hdr(token))
            if r.status_code == 408:
                print("   FAIL 408 OCR timeout")
                return
            if r.status_code == 422:
                print("   FAIL 422 OCR failed")
                return
            scan = r.json()
            print(f"   [{attempt+1}] status={scan['status']}")
            if scan["status"] == "completed":
                break
        else:
            print("   FAIL OCR không xong sau 60s")
            return

        ed = scan.get("extracted_data") or {}
        print(f"   OK extracted_data={ed}")
        print(f"   OK confidence_score={scan.get('confidence_score')}")

        # ── 5. Confirm → tạo contact ───────────────────────────────────────
        print("\n[5] CONFIRM")
        full_name = ed.get("full_name") or "Unknown"
        r = await c.post(
            f"{BASE}/scans/{scan_id}/confirm",
            headers=hdr(token),
            json={
                "confirmed_data": {
                    "full_name": full_name,
                    "company":   ed.get("company"),
                    "phone":     ed.get("phone"),
                    "email":     ed.get("email"),
                    "website":   ed.get("website"),
                    "address":   ed.get("address"),
                },
                "tag_ids": [],
                "event_id": None,
            },
        )
        assert r.status_code == 201, f"Confirm failed: {r.text}"
        contact = r.json()
        contact_id = contact["id"]
        print(f"   OK contact_id={contact_id}")
        print(f"   OK full_name={contact['full_name']}")
        print(f"   OK scan_id={contact['scan_id']}")
        print(f"   OK auto tag_ids={contact['tag_ids']}")

        # ── 6. Trigger enrichment ──────────────────────────────────────────
        print("\n[6] ENRICH — trigger")
        r = await c.post(f"{BASE}/enrichment/{contact_id}", headers=hdr(token))
        assert r.status_code == 202, f"Enrich trigger failed: {r.text}"
        print(f"   OK enrichment triggered, status={r.json()['status']}")

        print("\n[6b] ENRICH — poll result")
        for attempt in range(20):
            await asyncio.sleep(4)
            r = await c.get(f"{BASE}/enrichment/{contact_id}", headers=hdr(token))
            assert r.status_code == 200, f"Enrich poll failed: {r.text}"
            enrich = r.json()
            print(f"   [{attempt+1}] status={enrich['status']}")
            if enrich["status"] in ("completed", "failed"):
                break
        else:
            print("   FAIL Enrichment không xong sau 80s")

        if enrich["status"] == "completed":
            print(f"   OK brief={enrich.get('brief', '')[:80]}...")
            print(f"   OK keywords={enrich.get('keywords')}")
            print(f"   OK highlights={enrich.get('highlights')}")
            print(f"   OK linkedin_data={enrich.get('linkedin_data')}")
            print(f"   OK source={enrich.get('source')}")
        else:
            print(f"   FAIL enrichment status={enrich['status']}")

        # ── 7. Activity log ────────────────────────────────────────────────
        print("\n[7] ACTIVITY LOG")
        r = await c.get(f"{BASE}/activity/{contact_id}", headers=hdr(token))
        assert r.status_code == 200, f"Activity failed: {r.text}"
        logs = r.json()
        print(f"   OK {logs['total']} log entries")
        for log in logs["items"]:
            print(f"      action={log['action']}  source={log['source']}")

        # ── 8. Tạo digital card ────────────────────────────────────────────
        print("\n[8] CREATE DIGITAL CARD")
        import uuid
        slug = f"scantest-{uuid.uuid4().hex[:8]}"
        r = await c.post(
            f"{BASE}/cards/me",
            headers=hdr(token),
            json={
                "slug": slug,
                "display_name": full_name,
                "title": ed.get("position") or "Professional",
                "is_public": True,
                "links": {
                    "phone":   ed.get("phone"),
                    "website": ed.get("website"),
                },
            },
        )
        if r.status_code == 409:
            print("   Card already exists, skipping")
            r2 = await c.get(f"{BASE}/cards/me", headers=hdr(token))
            slug = r2.json()["slug"]
        else:
            assert r.status_code == 201, f"Card create failed: {r.text}"
            print(f"   OK slug={slug}")
            print(f"   OK qr_code_url={r.json()['qr_code_url']}")

        # ── 9. Public card view ────────────────────────────────────────────
        print("\n[9] PUBLIC CARD VIEW")
        r = await c.get(f"{BASE}/public/{slug}")
        assert r.status_code == 200, f"Public view failed: {r.text}"
        pub = r.json()
        print(f"   OK display_name={pub['display_name']}")
        print(f"   OK Sensitive fields hidden: user_id={'user_id' not in pub}, id={'id' not in pub}")

        # Check view_count tăng
        r2 = await c.get(f"{BASE}/cards/me", headers=hdr(token))
        print(f"   OK view_count={r2.json()['view_count']}")

        # ── 10. Cleanup ────────────────────────────────────────────────────
        print("\n[10] CLEANUP")
        r = await c.request(
            "DELETE",
            f"{BASE}/auth/me",
            headers=hdr(token),
            json={"password": USER["password"]},
        )
        assert r.status_code == 204, f"Cleanup failed: {r.text}"
        print("   OK User + all data deleted (cascade)")

        print("\n[PASS] FULL SCAN FLOW PASSED\n")


if __name__ == "__main__":
    asyncio.run(run())
