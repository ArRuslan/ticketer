from time import time

import pytest
from httpx import AsyncClient

from ticketer.utils.mfa import MFA
from . import create_test_user, create_session_token


@pytest.mark.asyncio
async def test_get_user_info(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.get("/users/me", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "mfa_enabled": user.mfa_key is not None,
    }


@pytest.mark.asyncio
async def test_edit_user_info(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    new_phone_number = 380_000_000_000 + int(time()) % 1_000_000_000
    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "email": f"1.{user.email}",
        "first_name": "ChangedFirst",
        "last_name": "ChangedLast",
        "password": "123456789",
        "new_password": "1234567890",
        "phone_number": new_phone_number,
    })
    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": f"1.{user.email}",
        "first_name": "ChangedFirst",
        "last_name": "ChangedLast",
        "phone_number": new_phone_number,
        "mfa_enabled": False,
    }


@pytest.mark.asyncio
async def test_edit_user_fail_password(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "email": f"1.{user.email}",
    })
    assert response.status_code == 400
    assert "password" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "email": f"1.{user.email}",
        "password": "1234567890",
    })
    assert response.status_code == 400
    assert "Wrong" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_get_payment_methods(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.get("/users/me/payment", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_add_delete_payment_method(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    card_number = "4532015112830366"
    expected_resp = {
        "type": "card",
        "card_number": card_number,
        "expiration_date": "12/99",
        "expired": False,
    }

    response = await client.post("/users/me/payment", headers={"Authorization": token}, json={
        "type": "card",
        "card_number": card_number,
        "expiration_date": "12/99",
    })
    assert response.status_code == 200, response.json()
    assert response.json() == expected_resp

    response = await client.get("/users/me/payment", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json() == [expected_resp]

    response = await client.delete(f"/users/me/payment/{card_number}", headers={"Authorization": token})
    assert response.status_code == 204

    response = await client.get("/users/me/payment", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_add_invalid_payment_method(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    card_number = "4532015112830367"

    response = await client.post("/users/me/payment", headers={"Authorization": token}, json={
        "type": "card",
        "card_number": card_number,
        "expiration_date": "12/99",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_enable_disable_mfa(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)
    mfa_key = "A"*16
    mfa = MFA(mfa_key)

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": None,
    })
    assert response.status_code == 400
    assert "disabled" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": mfa_key + "a",
    })
    assert response.status_code == 400
    assert "authentication key" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": mfa_key,
    })
    assert response.status_code == 400
    assert "authentication code" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": mfa_key,
        "mfa_code": "00000",
    })
    assert response.status_code == 400
    assert "authentication code" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": mfa_key,
        "mfa_code": mfa.getCode(),
    })
    assert response.status_code == 200
    assert response.json()["mfa_enabled"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": mfa_key,
        "mfa_code": mfa.getCode(),
    })
    assert response.status_code == 400
    assert "enabled" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": None,
    })
    assert response.status_code == 400
    assert "authentication code" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": None,
        "mfa_code": "00000",
    })
    assert response.status_code == 400
    assert "authentication code" in response.json()["error_message"]

    response = await client.patch("/users/me", headers={"Authorization": token}, json={
        "password": "123456789",
        "mfa_key": None,
        "mfa_code": mfa.getCode(),
    })
    assert response.status_code == 200
    assert not response.json()["mfa_enabled"]


