from time import time

import pytest
from httpx import AsyncClient

from tests import create_test_user, create_session_token
from ticketer.models import Location, Event, EventPlan, UserRole


async def create_events(count: int = 10):
    user = await create_test_user(role=UserRole.MANAGER)
    location = await Location.create(name="test", longitude=0, latitude=0)

    for i in range(count):
        event = await Event.create(
            name=f"Event {i}", description=f"Event {i}", category="test", city="test", location=location, manager=user
        )
        await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)


@pytest.mark.asyncio
async def test_event_pages(client: AsyncClient):
    await create_events()

    for page in (1, 2):
        response = await client.post("/events/search", json={}, params={"results_per_page": 5, "page": page})
        assert response.status_code == 200
        assert len(response.json()) == 5

    response = await client.post("/events/search", json={}, params={"results_per_page": 5, "page": 3})
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.asyncio
async def test_event_search_time(client: AsyncClient):
    await create_events()

    response = await client.post("/events/search", json={"time_max": int(time()) + 86400})
    assert response.status_code == 200
    assert len(response.json()) > 0

    response = await client.post("/events/search", json={"time_max": int(time()) - 86400})
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = await client.post("/events/search", json={"time_min": int(time()) + 86400})
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = await client.post("/events/search", json={"time_min": int(time()) - 86400})
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.asyncio
async def test_event_search_name(client: AsyncClient):
    await create_events(5)

    response = await client.post("/events/search", json={"name": "Event 3"})
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_event_with_event_plan(client: AsyncClient):
    await create_events(5)

    response = await client.post("/events/search", json={}, params={"with_plans": True})
    assert response.status_code == 200
    assert len(response.json()) > 0
    event = response.json()[0]
    assert len(event["plans"]) == 1

    response = await client.get(f"/events/{event['id']}", params={"with_plans": True})
    assert response.status_code == 200
    assert response.json() == event


@pytest.mark.asyncio
async def test_get_manager_events(client: AsyncClient):
    user = await create_test_user(role=UserRole.MANAGER)
    token = await create_session_token(user)

    response = await client.get(f"/admin/events", headers={"authorization": token})
    assert response.status_code == 200
    assert len(response.json()) == 0

    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(
        name=f"Test event", description=f"test", category="test", location=location, city="test", manager=user
    )
    await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)

    response = await client.get(f"/admin/events", headers={"authorization": token})
    assert response.status_code == 200
    assert len(response.json()) == 1
