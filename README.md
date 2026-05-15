# Cardly — Backend API

AI-powered business card scanner and smart contact management system.
Built during TIC Internship Summer 2026 (May – July 2026).

## Overview

Cardly lets users scan physical business cards via OCR, manage contacts, organize them with tags and events, enrich contact profiles with AI-gathered social data, and share a personal digital card via a public URL.

### Team

| Person | Modules |
|--------|---------|
| Huy | Auth, Contacts, Scans, OCR, Error Handling, Docker |
| Khanh | Tags, Events, Activity, Enrichment, Cards, Users, Uploads |
| Both | Core, Database, Models, Tests, Deploy |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11 |
| Framework | FastAPI 0.111 + Pydantic v2 |
| Database | MongoDB Atlas via Motor (fully async) |
| Auth | JWT access token (30 min) + HttpOnly refresh cookie (7 days) |
| Storage | Google Cloud Storage |
| AI | Gemini API (enrichment pipeline) |
| Rate limiting | slowapi |
| QR codes | qrcode[pil] |

---

## Setup

```bash
# 1. Clone and install
git clone https://github.com/ZackVN04/Cardly.git
cd Cardly
pip install -r requirements/dev.txt

# 2. Configure environment
cp .env.example .env
# Fill in: MONGODB_URL, JWT_SECRET, REFRESH_SECRET,
#          GCP_BUCKET, GCP_CREDENTIALS_JSON, GEMINI_API_KEY, FRONTEND_URL

# 3. Run
uvicorn src.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

All endpoints are prefixed with `/api/v1`.

---

## Project Structure

```
src/
├── core/           config · security · pagination · rate_limit · exceptions
├── auth/           signup · signin · JWT tokens · password reset · cascade delete
├── users/          public profile · search
├── uploads/        avatar → Google Cloud Storage
├── contacts/       CRUD · tag ops · text search · pagination
├── tags/           CRUD · bulk cleanup on delete
├── events/         CRUD · linked contacts ($lookup) · cascade on delete
├── activity/       append-only audit log · filter by action / contact
├── scans/          image upload · OCR (Vertex AI) · confirm → create contact
├── enrichment/     AI social data pipeline · Gemini · manual edit
├── cards/          digital card · QR code · public slug URL
├── database.py     Motor client · 8 collection getters · create_indexes
└── main.py         FastAPI app · CORS · lifespan · exception handlers
```

---

## Modules Implemented (Khanh)

### Tags — `/api/v1/tags`

Organize contacts with colored labels. Tag deletion performs a bulk `$pull` across all contacts atomically so no orphan `tag_ids` remain.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tags/` | List all tags (paginated) |
| `POST` | `/tags/` | Create tag — 409 if name already exists for this user |
| `PATCH` | `/tags/{tagId}` | Update name / color |
| `DELETE` | `/tags/{tagId}` | Delete tag + bulk remove from all contacts (`$pull`) |

**Key behavior:** `delete_with_bulk_pull` runs the contact cleanup and tag deletion concurrently via `asyncio.gather`.

---

### Events — `/api/v1/events`

Group contacts by networking events. Deleting an event nullifies `event_id` on all linked contacts (cascade, no orphans).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/events/` | List events sorted by `event_date` desc (paginated) |
| `POST` | `/events/` | Create event |
| `GET` | `/events/{eventId}` | Event detail + linked contacts paginated (`$lookup` aggregation) |
| `PATCH` | `/events/{eventId}` | Update event fields |
| `DELETE` | `/events/{eventId}` | Delete event + `$set event_id=null` on linked contacts |

---

### Activity Logs — `/api/v1/activity`

Append-only audit trail. Every write in the system (create, update, delete, enrich, tag) calls the shared `log_action()` helper which records `changed_fields`, `previous_values`, and `new_values`. No write endpoint is exposed — logs are written internally.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/activity/` | All logs for current user — filter by `action` and/or `contact_id` |
| `GET` | `/activity/{contactId}` | All logs for a specific contact |

**Recorded actions:** `created` · `updated` · `enriched` · `tagged` · `deleted`

---

### Enrichment — `/api/v1/enrichment`

Async AI pipeline that enriches a contact with social profile data using Gemini. Trigger returns `202 Accepted` immediately; the background task fetches LinkedIn / website / Facebook data, calls Gemini to generate a brief, keywords, and highlights, then persists the result. Poll `GET /{contactId}` for status.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/enrichment/` | List all enrichment results (filterable by status) |
| `POST` | `/enrichment/{contactId}` | Trigger AI enrichment — 202 Accepted · 409 if already running · rate limit 5/min |
| `GET` | `/enrichment/{contactId}` | Poll result (`pending` → `processing` → `completed` / `failed`) |
| `PATCH` | `/enrichment/{contactId}` | Manual edit — sets `source = "manual"` automatically |
| `DELETE` | `/enrichment/{contactId}` | Delete result + write activity log |

**Pipeline status flow:** `processing` → `completed` (or `failed` on error)

**Result shape:**
```json
{
  "brief": "2–4 sentence professional summary",
  "keywords": ["AI startup", "Series A"],
  "highlights": ["Raised Series A", "10+ years engineering"],
  "linkedin_data": { "connections": 500, "current_role": "...", ... },
  "facebook_data": { "followers": 1200, "recent_posts": [...] },
  "website_data": { "about": "...", "founded": "2020", "team_size": "50+" },
  "source": "gemini",
  "status": "completed"
}
```

---

### Digital Cards — `/api/v1/cards`

Each user can create one digital card reachable at a public URL. Creating a card generates a QR code PNG, uploads it to GCS, and stores the CDN URL. `view_count` is incremented atomically on every public visit.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/cards/me` | Required | Get own card |
| `POST` | `/cards/me` | Required | Create card — 409 if one already exists |
| `PATCH` | `/cards/me` | Required | Update card — QR regenerated if slug changes |
| `DELETE` | `/cards/me` | Required | Delete card, slug freed |
| `GET` | `/public/{slug}` | None | Public card view — 404 if `is_public=false` · increments `view_count` |

**Slug rules:** `^[a-z0-9][a-z0-9-]{2,29}$` enforced at validation. Unique across all users.

---

### Users — `/api/v1/users`

Public profile lookup and search. Only safe fields are returned — no password hash, no `is_active`, no internal IDs beyond `id`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/users/me` | Own public profile |
| `GET` | `/users/search?q=` | Atlas full-text search across username + full_name |
| `GET` | `/users/{userId}` | Any user's public profile |

---

### Uploads — `/api/v1/uploads`

Avatar upload to Google Cloud Storage. Old avatar is deleted from GCS after the DB update succeeds (fire-and-forget). Stores `avatar_blob_name` separately from the URL so GCS cleanup doesn't depend on URL parsing.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/uploads/avatar` | Upload avatar image — max 5 MB · JPEG / PNG / WebP only |

**Validation:** 413 if file too large, 415 if unsupported MIME type, 503 if GCS upload fails.

---

## Shared Infrastructure (Both)

### Core (`src/core/`)

| File | Purpose |
|------|---------|
| `config.py` | `Settings` via pydantic-settings — all values loaded from `.env` |
| `security.py` | `hash_password` / `verify_password` — bcrypt, salt rounds 12 |
| `pagination.py` | `PaginatedResponse[T]` generic — `items, total, skip, limit, pages` |
| `rate_limit.py` | slowapi `Limiter` — 10/min on `/scans`, 5/min on `/enrichment` |
| `exceptions.py` | Global handlers — standardized 422 Pydantic format, 404/403/401 |

### Database (`src/database.py`)

Motor async client. Exports one getter per collection plus `create_indexes()` which sets up all unique, text, and compound indexes on startup.

**Collections:** `users` · `contacts` · `events` · `tags` · `business_card_scans` · `enrichment_results` · `digital_cards` · `contact_activity_logs`

---

## Full Workflow

```
1. User registers / logs in  →  JWT access token + HttpOnly refresh cookie

2. Upload avatar             →  POST /uploads/avatar  →  GCS → avatar_url stored

3. Scan business card        →  POST /scans           →  OCR async (Vertex AI)
                             →  GET  /scans/{id}       →  poll until status=completed
                             →  POST /scans/{id}/confirm → contact created with scan_id

4. Manage contacts           →  POST/GET/PATCH/DELETE /contacts
   Tag contacts              →  POST /contacts/{id}/tags
   Assign to event           →  PATCH /contacts/{id}  { event_id }

5. Organize tags             →  POST /tags             →  create label
                             →  DELETE /tags/{id}      →  auto-cleans all contacts

6. Track events              →  POST /events           →  create event
                             →  GET  /events/{id}      →  event + linked contacts

7. Enrich contact            →  POST /enrichment/{contactId}   →  202 Accepted
                             →  GET  /enrichment/{contactId}   →  poll status
                             →  Result: brief + keywords + social data from Gemini

8. Create digital card       →  POST /cards/me         →  slug + QR generated
                             →  GET  /public/{slug}    →  public view, no auth

9. Audit trail               →  GET  /activity/        →  all changes logged
                             →  GET  /activity/{contactId}
```

---

## API Reference Summary

| Module | Base Path | Endpoints |
|--------|-----------|-----------|
| Auth | `/api/v1/auth` | signup · signin · signout · refresh · me GET/PATCH · password · forgot · reset · DELETE/me |
| Users | `/api/v1/users` | me · search · {userId} |
| Uploads | `/api/v1/uploads` | avatar |
| Contacts | `/api/v1/contacts` | CRUD · tags sub-resource |
| Tags | `/api/v1/tags` | CRUD |
| Events | `/api/v1/events` | CRUD · detail with contacts |
| Activity | `/api/v1/activity` | list all · list by contact |
| Scans | `/api/v1/scans` | upload · poll · correct · confirm · delete |
| Enrichment | `/api/v1/enrichment` | trigger · poll · manual edit · delete |
| Cards | `/api/v1/cards` | CRUD (auth) · public slug (no auth) |

---

## Testing

```bash
# Run all tests
pytest

# Run a specific module
pytest tests/uploads/
pytest tests/users/
pytest tests/enrichment/
```

Tests use `asyncio_mode = "auto"` and the `async_client` fixture which connects to a real MongoDB Atlas test database — no mocking of the database layer. AI calls (Gemini, OCR) are mocked via `mock_enrich()` when `ENVIRONMENT=test`.

**Coverage target:** > 80% across all modules.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MONGODB_URL` | MongoDB Atlas connection string |
| `JWT_SECRET` | Access token signing secret |
| `REFRESH_SECRET` | Refresh token signing secret |
| `GCP_BUCKET` | Google Cloud Storage bucket name |
| `GCP_CREDENTIALS_JSON` | GCP service account JSON (path or inline) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `FRONTEND_URL` | Allowed CORS origin |
| `ENVIRONMENT` | `development` / `test` / `production` |
