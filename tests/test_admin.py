from base64 import b64encode
from datetime import datetime, UTC
from time import time

import pytest
from httpx import AsyncClient
from pyvips import Image

from tests import create_test_user, create_session_token
from ticketer.models import UserRole, Location, Event


image16: bytes = Image.black(16, 16).write_to_buffer(".jpg[Q=85]")
image24: bytes = Image.black(24, 24).write_to_buffer(".jpg[Q=85]")


@pytest.mark.asyncio
async def test_insufficient_privileges(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.post("/admin/users", headers={"Authorization": token})
    assert response.status_code == 403

    response = await client.post("/admin/events", headers={"Authorization": token})
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
async def test_ban_unban_admin(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.post(f"/admin/users/{user.id}/ban", headers={"Authorization": token})
    assert response.status_code == 403
    assert "cannot" in response.json()["error_message"]

    response = await client.post(f"/admin/users/{user.id}/unban", headers={"Authorization": token})
    assert response.status_code == 403
    assert "cannot" in response.json()["error_message"]


@pytest.mark.asyncio
async def test_ban_unban_nonexistent_user(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.post(f"/admin/users/{user.id+1000}/ban", headers={"Authorization": token})
    assert response.status_code == 404

    response = await client.post(f"/admin/users/{user.id+1000}/unban", headers={"Authorization": token})
    assert response.status_code == 404


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
        "city": "test",
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
        "image_id": None,
        "city": "test",
        "location": {
            "name": location.name,
            "longitude": location.longitude,
            "latitude": location.latitude,
        },
    }


@pytest.mark.asyncio
async def test_create_event_fail_unknown_location(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    start_time = int(time()+123)
    response = await client.post("/admin/events", headers={"Authorization": token}, json={
        "name": "Test Event",
        "description": "This is test event",
        "category": "concert",
        "start_time": start_time,
        "end_time": start_time+60,
        "location_id": 123456,
        "image": None,
        "city": "test",
        "plans": [{"name": "Test plan", "price": 123456, "max_tickets": 5}],
    })
    assert response.status_code == 404
    assert "location" in response.json()["error_message"]


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
        city="test",
        start_time=now,
        end_time=now,
        location=location,
        manager=user,
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
    assert response.status_code == 200, response.json()
    assert response.json() == {
        "id": event.id,
        "name": "Test Event 1",
        "description": "This is test event 1",
        "category": "concert1",
        "start_time": now,
        "end_time": now,
        "image_id": None,
        "city": "test",
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
        city="test",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        location=location,
        manager=user,
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


@pytest.mark.asyncio
async def test_create_update_event_with_image(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=1)

    response = await client.post("/admin/events", headers={"Authorization": token}, json={
        "name": "Test Event",
        "description": "This is test event",
        "category": "concert",
        "start_time": int(time()),
        "end_time": int(time()),
        "location_id": location.id,
        "city": "test",
        "image": f"data:image/jpg;base64,{b64encode(image16).decode('utf8')}",
        "plans": [{"name": "Test plan", "price": 123456, "max_tickets": 5}],
    })
    assert response.status_code == 200, response.json()
    resp = response.json()
    assert resp["image_id"] is not None
    event_id = resp["id"]
    old_image_id = resp["image_id"]

    response = await client.patch(f"/admin/events/{event_id}", headers={"Authorization": token}, json={
        "image": f"data:image/jpg;base64,{b64encode(image24).decode('utf8')}",
    })
    assert response.status_code == 200
    resp = response.json()
    assert resp["image_id"] is not None
    assert resp["image_id"] != old_image_id

    response = await client.patch(f"/admin/events/{event_id}", headers={"Authorization": token}, json={
        "image": None,
    })
    assert response.status_code == 200
    resp = response.json()
    assert resp["image_id"] is None


@pytest.mark.asyncio
async def test_edit_user(client: AsyncClient):
    test_user = await create_test_user()

    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.patch(f"/admin/users/{test_user.id}", headers={"Authorization": token}, json={
        "mfa_enabled": False,
        "avatar": f"data:image/jpg;base64,{b64encode(image24).decode('utf8')}",
    })
    assert response.status_code == 200, response.json()
    j = response.json()
    assert not j["mfa_enabled"]
    assert j["avatar_id"] is not None


@pytest.mark.asyncio
async def test_edit_role_fail(client: AsyncClient):
    test_user = await create_test_user(role=UserRole.ADMIN)
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.patch(f"/admin/users/{test_user.id}", headers={"Authorization": token}, json={
        "role": UserRole.USER
    })
    assert response.status_code == 400

    await test_user.update(role=UserRole.USER)

    response = await client.patch(f"/admin/users/{test_user.id}", headers={"Authorization": token}, json={
        "role": UserRole.ADMIN
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_nonexistent_user(client: AsyncClient):
    user = await create_test_user(role=UserRole.ADMIN)
    token = await create_session_token(user)

    response = await client.patch(f"/admin/users/{user.id+1000}", headers={"Authorization": token}, json={})
    assert response.status_code == 404
