import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app

# Implementation: Phase 4 — W9 (Both)
# async_client fixture, mock_db, create_test_user(), create_test_token(), cleanup()


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
