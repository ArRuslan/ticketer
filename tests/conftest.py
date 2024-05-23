from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient

from tests._s3_server import s3_server
from ticketer import config

config.DB_CONNECTION_STRING = "sqlite://:memory:"

from ticketer.main import app


@pytest_asyncio.fixture
async def app_with_lifespan() -> FastAPI:
    async with LifespanManager(app) as manager:
        yield manager.app


@pytest_asyncio.fixture
async def client(app_with_lifespan) -> AsyncClient:
    async with AsyncClient(app=app_with_lifespan, base_url="https://ticketer.test") as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def fake_s3_server():
    Path("data/tests/files/ticketer").mkdir(parents=True, exist_ok=True)

    config.S3._access_key_id = "1"
    config.S3._secret_access_key = "1"
    config.S3._endpoint = "http://127.0.0.1:10001"
    with s3_server().run_in_thread():
        yield
