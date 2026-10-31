import os

# Must be set before the app is imported (settings are read at import time).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_baggage.db"
os.environ["SECRET_KEY"] = "test-secret-test-secret-test-secret-123456"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "false"
os.environ["ALLOWED_ORIGINS"] = "[]"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.rate_limit import RateLimit  # noqa: E402
from app.database.base import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

API = "/api"

SIGNUP = {
    "name": "John Doe",
    "email": "John@Gmail.com",
    "password": "correct-horse-battery",
    "phone": "123-456-7890",
}
BAG = {
    "name": "My Laptop Bag",
    "category": "luggage",
    "color": "#000000",
    "brand": "BrandName",
    "remarks": "This is my favorite bag.",
}


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    RateLimit.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()


async def register(client: AsyncClient, **overrides) -> dict:
    r = await client.post(f"{API}/signUp", json={**SIGNUP, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}


async def create_bag(client: AsyncClient, tokens: dict, **overrides) -> dict:
    r = await client.post(f"{API}/baggage", headers=auth(tokens), json={**BAG, **overrides})
    assert r.status_code == 201, r.text
    return r.json()
