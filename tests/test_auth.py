from time import time

import pytest
from httpx import AsyncClient

from ticketer import config
from ticketer.utils.mfa import MFA
from .conftest import create_test_user


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/auth/register", json={
        "email": f"test{time()}@gmail.com",
        "password": "123456789",
        "captcha_key": "should-pass",
        "first_name": "TestFirst",
        "last_name": "TestLast",
    })
    assert response.status_code == 200, response.json()
    assert response.json().keys() == {"token", "expires_at"}


@pytest.mark.asyncio
async def test_register_captcha_fail(client: AsyncClient):
    config.TURNSTILE_SECRET = "2x0000000000000000000000000000000AA"

    response = await client.post("/auth/register", json={
        "email": f"test{time()}@gmail.com",
        "password": "123456789",
        "captcha_key": "should-not-pass",
        "first_name": "_",
        "last_name": "_",
    })
    assert response.status_code == 400
    assert "captcha" in response.json()["error_message"]

    config.TURNSTILE_SECRET = "1x0000000000000000000000000000000AA"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    email = f"test{time()}@gmail.com"
    response = await client.post("/auth/register", json={
        "email": email,
        "password": "123456789",
        "captcha_key": "should-pass",
        "first_name": "_",
        "last_name": "_",
    })
    assert response.status_code == 200

    response = await client.post("/auth/register", json={
        "email": email,
        "password": "123456789",
        "captcha_key": "should-pass",
        "first_name": "_",
        "last_name": "_",
    })
    assert response.status_code == 400
    assert "already exists" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    user = await create_test_user()

    response = await client.post("/auth/login", json={
        "email": user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 200, response.json()
    assert response.json().keys() == {"token", "expires_at"}


@pytest.mark.asyncio
async def test_login_captcha_fail(client: AsyncClient):
    user = await create_test_user()

    config.TURNSTILE_SECRET = "2x0000000000000000000000000000000AA"
    response = await client.post("/auth/login", json={
        "email": user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 400
    assert "captcha" in response.json()["error_message"]
    config.TURNSTILE_SECRET = "1x0000000000000000000000000000000AA"


@pytest.mark.asyncio
async def test_login_creds_fail(client: AsyncClient):
    user = await create_test_user()

    response = await client.post("/auth/login", json={
        "email": f"1.{user.email}",
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 400
    assert "Wrong" in response.json()["error_message"]

    response = await client.post("/auth/login", json={
        "email": user.email,
        "password": "1234567890",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 400
    assert "Wrong" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_login_mfa(client: AsyncClient):
    user = await create_test_user()
    await user.update(mfa_key="A"*16)

    response = await client.post("/auth/login", json={
        "email": user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 400
    assert "two-factor" in response.json()["error_message"]

    mfa = MFA(user.mfa_key)
    response = await client.post("/auth/login", json={
        "email": user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
        "mfa_code": mfa.getCode(),
    })
    assert response.status_code == 200, response.json()
