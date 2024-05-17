from time import time

import pytest_asyncio
from asgi_lifespan import LifespanManager
from bcrypt import hashpw, gensalt
from httpx import AsyncClient

from ticketer.main import app
from ticketer.models import User, AuthSession


@pytest_asyncio.fixture
async def app_with_lifespan():
    async with LifespanManager(app) as manager:
        yield manager.app


@pytest_asyncio.fixture
async def client(app_with_lifespan) -> AsyncClient:
    async with AsyncClient(app=app_with_lifespan, base_url="https://ticketer.test") as client:
        yield client


async def create_test_user(email: str | None = None, password: str | None = None) -> User:
    email = email or f"test.{time()}@ticketer.com"
    password = (password or "123456789").encode("utf8")

    password_hash = hashpw(password, gensalt(rounds=4)).decode()

    return await User.create(
        email=email, password=password_hash, first_name="Test", last_name="Test"
    )


async def create_session_token(user: User) -> str:
    session = await AuthSession.create(user=user)
    return session.to_jwt()
