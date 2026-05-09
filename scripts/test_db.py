"""
Chạy: python test_db.py
Mục đích: kiểm tra kết nối MongoDB Atlas độc lập với FastAPI.
"""

import asyncio
import sys

from dotenv import dotenv_values

config = dotenv_values(".env")
url = config.get("MONGODB_URL") or config.get("mongodb_url")

if not url:
    print("[FAIL] Không tìm thấy MONGODB_URL trong file .env")
    sys.exit(1)

print(f"[INFO] Đang kết nối tới: {url[:40]}...")


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    # Thử kết nối thường
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)
    try:
        info = await client.server_info()
        print(f"[OK] Kết nối thành công! MongoDB version: {info['version']}")
        return
    except Exception as e:
        print(f"[FAIL] Kết nối thường thất bại: {e}")
    finally:
        client.close()

    # Thử với tlsAllowInvalidCertificates (bypass SSL cert errors trên Windows)
    print("[INFO] Thử lại với tlsAllowInvalidCertificates=True ...")
    client2 = AsyncIOMotorClient(
        url,
        serverSelectionTimeoutMS=8000,
        tlsAllowInvalidCertificates=True,
    )
    try:
        info = await client2.server_info()
        print(f"[OK] Kết nối thành công với tlsAllowInvalidCertificates!")
        print("[ACTION] Thêm tlsAllowInvalidCertificates=True vào AsyncIOMotorClient trong src/database.py")
    except Exception as e:
        print(f"[FAIL] Vẫn thất bại: {e}")
        print()
        print("Các nguyên nhân có thể:")
        print("  1. IP của bạn chưa được whitelist trên MongoDB Atlas")
        print("     → Vào Atlas > Network Access > Add Current IP Address")
        print("  2. Username/password sai trong MONGODB_URL")
        print("  3. Cluster đang bị tắt hoặc paused trên Atlas")
    finally:
        client2.close()


asyncio.run(main())
