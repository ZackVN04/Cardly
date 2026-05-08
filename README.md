# Cardly – Backend API

FastAPI backend cho **Cardly** — ứng dụng scan danh thiếp & quản lý liên hệ thông minh.

## Yêu cầu

- Python 3.11+
- Git

## Bắt đầu nhanh

```bash
# 1. Clone repo
git clone https://github.com/ZackVN04/Cardly.git
cd Cardly

# 2. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 3. Cài dependencies
pip install -r requirements/dev.txt

# 4. Tạo file .env từ template
cp .env.example .env
# Mở .env và điền JWT_SECRET, REFRESH_SECRET (giữ nguyên MONGODB_URL)

# 5. Chạy server
uvicorn src.main:app --reload
```

Server chạy tại: http://localhost:8000
API docs: http://localhost:8000/docs

## Chạy bằng Docker

```bash
cp .env.example .env
docker compose up --build
```

## Chạy tests

```bash
pytest
pytest --cov=src        # với coverage report
```

## Cấu trúc project

```
src/
├── main.py             # FastAPI app, middleware, lifespan
├── database.py         # MongoDB Atlas connection (Motor), indexes
├── models.py           # PyObjectId, BaseDocument
├── core/               # config, exceptions, security, rate limit, pagination
├── auth/               # JWT auth — đăng ký, đăng nhập, refresh token
├── contacts/           # CRUD danh bạ
├── tags/               # Quản lý tags
├── events/             # Quản lý sự kiện (nơi gặp gỡ)
├── scans/              # Upload + OCR danh thiếp
├── enrichment/         # AI agent làm giàu thông tin liên hệ
├── cards/              # Digital business card (public profile)
├── users/              # User profile + search
├── uploads/            # Avatar upload
└── activity/           # Activity log
```

## Phân công

| Module | Người phụ trách | Tuần |
|---|---|---|
| auth | Huy | W5 |
| contacts | Huy | W4 |
| scans (OCR) | Huy | W6 |
| events | Khanh | W4 |
| tags | Khanh | W4 |
| users + uploads | Khanh | W5 |
| enrichment (AI) | Khanh | W6–W7 |
| cards (digital card) | Khanh | W8 |
| activity log | Khanh | W6 |
| tests | Cả hai | W9 |

## Biến môi trường

Xem [.env.example](.env.example) để biết đầy đủ các biến cần thiết.

| Biến | Mô tả |
|---|---|
| `MONGODB_URL` | MongoDB Atlas connection string (team dùng chung) |
| `JWT_SECRET` | Secret để ký access token — tự đặt, dài ≥ 32 ký tự |
| `REFRESH_SECRET` | Secret để ký refresh token — tự đặt, dài ≥ 32 ký tự |
| `GEMINI_API_KEY` | API key Google Gemini (dùng cho enrichment) |
| `ENVIRONMENT` | `dev` / `staging` / `production` |
