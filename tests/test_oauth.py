from os import urandom

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock

from . import create_test_user
from . import google_oauth_token_exchange, google_oauth_user_info, create_session_token


def register_http_mock(mock: HTTPXMock) -> tuple[str, str]:
    correct_code = urandom(16).hex()
    correct_token = urandom(32).hex()
    mock.add_callback(
        google_oauth_token_exchange(correct_code, correct_token),
        url="https://accounts.google.com/o/oauth2/token"
    )
    mock.add_callback(
        google_oauth_user_info(correct_token),
        url="https://www.googleapis.com/oauth2/v1/userinfo"
    )

    return correct_code, correct_token


@pytest.mark.asyncio
async def test_google_register(client: AsyncClient, httpx_mock: HTTPXMock):
    correct_code, correct_token = register_http_mock(httpx_mock)

    response = await client.get("/auth/google")
    assert response.status_code == 200

    response = await client.post("/auth/google/callback", json={
        "code": correct_code,
    })
    assert response.status_code == 200, response.json()
    assert response.json().keys() == {"token", "expires_at", "connect"}
    assert not response.json()["connect"]


@pytest.mark.asyncio
async def test_connect_and_login(client: AsyncClient, httpx_mock: HTTPXMock):
    correct_code, correct_token = register_http_mock(httpx_mock)
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.post("/auth/google/connect", headers={"Authorization": token})
    assert response.status_code == 200
    url = response.json()["url"]
    params = {param.split("=")[0]: param.split("=")[1] for param in url.split("?")[1].split("&")}
    state = params["state"]

    response = await client.post("/auth/google/callback", json={
        "code": correct_code,
        "state": state,
    })
    assert response.status_code == 200, response.json()
    assert response.json().keys() == {"token", "expires_at", "connect"}
    assert response.json()["connect"]

    response = await client.post("/auth/google/connect", headers={"Authorization": token})
    assert response.status_code == 400

    response = await client.post("/auth/google/callback", json={
        "code": correct_code,
        "state": state,
    })
    assert response.status_code == 400
    assert "already" in response.json()["error_message"]

