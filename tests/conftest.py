import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.database import connect_db, create_indexes, disconnect_db


@pytest_asyncio.fixture
async def async_client():
    await connect_db()
    await create_indexes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await disconnect_db()
