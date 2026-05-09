"""
W3 integration tests — main.py
Tests cover: app instance, router modules importable with correct prefix,
global exception handler format, CORS middleware.
"""
from fastapi import FastAPI

from src.main import app


# ---------------------------------------------------------------------------
# App instance sanity
# ---------------------------------------------------------------------------


def test_app_is_fastapi_instance():
    assert isinstance(app, FastAPI)


def test_app_title():
    assert app.title == "Cardly API"


def test_app_version():
    assert app.version == "1.0.0"


# ---------------------------------------------------------------------------
# Router modules: importable and have correct prefix configured
# ---------------------------------------------------------------------------


def test_auth_router_prefix():
    from src.auth.router import router
    assert router.prefix == "/auth"


def test_contacts_router_prefix():
    from src.contacts.router import router
    assert router.prefix == "/contacts"


def test_tags_router_prefix():
    from src.tags.router import router
    assert router.prefix == "/tags"


def test_events_router_prefix():
    from src.events.router import router
    assert router.prefix == "/events"


def test_scans_router_prefix():
    from src.scans.router import router
    assert router.prefix == "/scans"


def test_enrichment_router_prefix():
    from src.enrichment.router import router
    assert router.prefix == "/enrichment"


def test_cards_router_prefix():
    from src.cards.router import router
    assert router.prefix == "/cards"


def test_cards_public_router_exists():
    from src.cards.router import public_router
    assert public_router is not None


def test_users_router_prefix():
    from src.users.router import router
    assert router.prefix == "/users"


def test_uploads_router_prefix():
    from src.uploads.router import router
    assert router.prefix == "/uploads"


def test_activity_router_prefix():
    from src.activity.router import router
    assert router.prefix == "/activity"


# ---------------------------------------------------------------------------
# Global exception handler — 404 returns {"code": 404, "message": "..."}
# ---------------------------------------------------------------------------


async def test_404_returns_custom_json_format(async_client):
    response = await async_client.get("/api/v1/nonexistent-path-xyz")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 404
    assert "message" in body


async def test_404_has_no_extra_fields(async_client):
    response = await async_client.get("/completely-unknown")
    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"code", "message"}


# ---------------------------------------------------------------------------
# CORS — requests with Origin header get access-control header back
# ---------------------------------------------------------------------------


async def test_cors_includes_allow_origin_on_404(async_client):
    response = await async_client.get(
        "/api/v1/nonexistent",
        headers={"Origin": "http://localhost:3000"},
    )
    assert "access-control-allow-origin" in response.headers


async def test_cors_preflight_responds(async_client):
    response = await async_client.options(
        "/api/v1/auth/signup",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" in response.headers
