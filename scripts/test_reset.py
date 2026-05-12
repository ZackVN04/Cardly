"""Script test luồng forgot/reset password — chạy khi server đang chạy trên port 8000."""
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from src.auth.utils import create_reset_token
from src.core.config import settings

BASE = "http://127.0.0.1:8000/api/v1"
TEST_EMAIL = "resetflow@cardly.dev"
TEST_USER = "resetflow_test"


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL, tlsAllowInvalidCertificates=True)
    db = client[settings.MONGODB_DB_NAME]
    http = httpx.AsyncClient()

    # Cleanup trước
    await db["users"].delete_one({"username": TEST_USER})

    # 1. Signup
    r = await http.post(f"{BASE}/auth/signup", json={
        "username": TEST_USER, "email": TEST_EMAIL,
        "password": "Password123", "full_name": "Reset Flow Test",
    })
    assert r.status_code == 201, f"signup failed: {r.text}"
    print(f"[1] signup 201 OK  id={r.json()['id']}")

    # 2. forgot-password → server tạo token + lưu hash vào DB
    r = await http.post(f"{BASE}/auth/forgot-password", json={"email": TEST_EMAIL})
    assert r.status_code == 200 and r.json() == {}, f"forgot failed: {r.text}"
    print("[2] forgot-password 200 {} OK")

    # 3. Verify hash đã lưu trong DB
    user = await db["users"].find_one({"email": TEST_EMAIL})
    stored_hash = user.get("reset_token")
    assert stored_hash and len(stored_hash) == 64, "hash không hợp lệ"
    print(f"[3] reset_token hash in DB: {stored_hash[:16]}... OK")

    # 4. Tạo lại token để test (cùng logic với forgot_password)
    token = create_reset_token(TEST_EMAIL, settings.JWT_SECRET)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=15)
    await db["users"].update_one(
        {"email": TEST_EMAIL},
        {"$set": {"reset_token": token_hash, "reset_token_expiry": expiry}},
    )
    print(f"[4] token injected for test OK")

    # 5. reset-password
    r = await http.post(f"{BASE}/auth/reset-password", json={
        "token": token, "new_password": "ResetPass789",
    })
    assert r.status_code == 204, f"reset-password failed: {r.text}"
    print("[5] reset-password 204 OK")

    # 6. Signin với password mới
    r = await http.post(f"{BASE}/auth/signin", json={
        "username": TEST_USER, "password": "ResetPass789",
    })
    assert r.status_code == 200 and "access_token" in r.json(), f"signin failed: {r.text}"
    access = r.json()["access_token"]
    print("[6] signin với password mới 200 OK")

    # 7. Replay attack: dùng lại token cũ phải bị từ chối (reset_token=None sau bước 5)
    r = await http.post(f"{BASE}/auth/reset-password", json={
        "token": token, "new_password": "AnotherPass000",
    })
    assert r.status_code == 400, f"replay không bị chặn! status={r.status_code}"
    print(f"[7] replay attack blocked 400 OK  detail={r.json().get('detail','')}")

    # 8. reset_token field đã bị xóa khỏi DB
    user_after = await db["users"].find_one({"email": TEST_EMAIL})
    assert user_after["reset_token"] is None, "reset_token chưa được clear"
    print("[8] reset_token cleared in DB OK")

    # Cleanup
    r = await http.request("DELETE", f"{BASE}/auth/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"password": "ResetPass789"},
    )
    assert r.status_code == 204, f"cleanup failed: {r.text}"
    print("[9] cleanup DELETE /me 204 OK")

    await http.aclose()
    client.close()
    print("\nALL PASS Tất cả 9 bước PASS — forgot/reset flow hoàn chỉnh")


if __name__ == "__main__":
    asyncio.run(main())
