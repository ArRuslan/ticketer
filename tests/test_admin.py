from datetime import datetime, UTC
from time import time

import pytest
from httpx import AsyncClient

from ticketer.models import UserRole, Location, Event
from .conftest import create_test_user, create_session_token


@pytest.mark.asyncio
async def test_insufficient_privileges(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.post("/admin/users", headers={"Authorization": token})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient):
    test_user = await create_test_user()
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.post("/admin/users", headers={"Authorization": token}, json={})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0] == {
        "id": test_user.id,
        "email": test_user.email,
        "has_password": True,
        "first_name": test_user.first_name,
        "last_name": test_user.last_name,
        "avatar_id": test_user.avatar_id,
        "phone_number": test_user.phone_number,
        "mfa_enabled": False,
        "banned": test_user.banned,
        "role": test_user.role,
    }


@pytest.mark.asyncio
async def test_ban_unban_user(client: AsyncClient):
    test_user = await create_test_user()

    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.post(f"/admin/users/{test_user.id}/ban", headers={"Authorization": token})
    assert response.status_code == 204

    response = await client.post("/auth/login", json={
        "email": test_user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 403
    assert "banned" in response.json()["error_message"]

    response = await client.post(f"/admin/users/{test_user.id}/unban", headers={"Authorization": token})
    assert response.status_code == 204

    response = await client.post("/auth/login", json={
        "email": test_user.email,
        "password": "123456789",
        "captcha_key": "should-pass",
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ban_admin(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.post(f"/admin/users/{user.id}/ban", headers={"Authorization": token})
    assert response.status_code == 403
    assert "cannot" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_create_event(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=1)

    start_time = int(time()+123)
    response = await client.post("/admin/events", headers={"Authorization": token}, json={
        "name": "Test Event",
        "description": "This is test event",
        "category": "concert",
        "start_time": start_time,
        "end_time": start_time+60,
        "location_id": location.id,
        "image": None,
        "plans": [{"name": "Test plan", "price": 123456, "max_tickets": 5}],
    })
    assert response.status_code == 200
    resp = response.json()
    del resp["id"]
    assert resp == {
        "name": "Test Event",
        "description": "This is test event",
        "category": "concert",
        "start_time": start_time,
        "end_time": start_time+60,
        "location": {
            "name": location.name,
            "longitude": location.longitude,
            "latitude": location.latitude,
        },
    }


@pytest.mark.asyncio
async def test_edit_event(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=1)
    location2 = await Location.create(name="test2", longitude=2, latitude=3)
    now = datetime.now(UTC)
    event = await Event.create(
        name="Test Event",
        description="This is test event",
        category="concert",
        start_time=now,
        end_time=now,
        location=location,
    )

    now = int(datetime.now(UTC).timestamp())
    response = await client.patch(f"/admin/events/{event.id}", headers={"Authorization": token}, json={
        "name": "Test Event 1",
        "description": "This is test event 1",
        "category": "concert1",
        "start_time": now,
        "end_time": now,
        "location_id": location2.id,
        "plans": [{"name": "Test plan 1", "price": 123456, "max_tickets": 5}],
    })
    assert response.status_code == 200
    assert response.json() == {
        "id": event.id,
        "name": "Test Event 1",
        "description": "This is test event 1",
        "category": "concert1",
        "start_time": now,
        "end_time": now,
        "location": {
            "name": location2.name,
            "longitude": location2.longitude,
            "latitude": location2.latitude,
        },
    }


@pytest.mark.asyncio
async def test_edit_event_fail_unknown_location(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=1)
    event = await Event.create(
        name="Test Event",
        description="This is test event",
        category="concert",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        location=location,
    )

    response = await client.patch(f"/admin/events/{event.id}", headers={"Authorization": token}, json={
        "location_id": location.id+1000,
    })
    assert response.status_code == 404
    assert "location" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_edit_event_fail_unknown_event(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.patch(f"/admin/events/123456", headers={"Authorization": token}, json={
        "name": "Test",
    })
    assert response.status_code == 404
    assert "event" in response.json()["error_message"]
