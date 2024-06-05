from datetime import datetime, UTC

import pytest
from httpx import AsyncClient

from tests import create_test_user, create_session_token
from ticketer.config import fcm
from ticketer.models import Location, Event, EventPlan, PaymentState, Ticket, Payment, UserRole, UserDevice


@pytest.mark.asyncio
async def test_full_purchase(client: AsyncClient):
    user = await create_test_user()
    manager = await create_test_user(role=UserRole.MANAGER)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(
        name=f"Test event", description=f"test", category="test", location=location, city="test", manager=manager
    )
    plan = await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)

    response = await client.post("/users/me/devices", headers={"Authorization": token}, json={
        "device_token": "123",
    })
    assert response.status_code == 204

    async def empty(*args, **kwargs):
        pass

    fcm.send_message = empty

    response = await client.post("/tickets/request-payment", headers={"Authorization": token}, json={
        "event_id": event.id,
        "plan_id": plan.id,
        "amount": 2000,
    })
    assert response.status_code == 400

    response = await client.post("/tickets/request-payment", headers={"Authorization": token}, json={
        "event_id": event.id,
        "plan_id": plan.id,
    })
    assert response.status_code == 200
    ticket_id = response.json()["ticket_id"]

    response = await client.get(f"/tickets/{ticket_id}/check-verification", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json()["payment_state"] == PaymentState.AWAITING_VERIFICATION

    response = await client.get(f"/tickets/pending-confirmations", headers={"Authorization": token})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = await client.post(f"/tickets/{ticket_id}/verify-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 204
    response = await client.post(f"/tickets/{ticket_id}/verify-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 400

    response = await client.get(f"/tickets/pending-confirmations", headers={"Authorization": token})
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = await client.get(f"/tickets/{ticket_id}/check-verification", headers={"Authorization": token})
    assert response.status_code == 200
    j = response.json()
    assert j["payment_state"] == PaymentState.AWAITING_PAYMENT
    paypal_id = j["paypal_id"]
    assert paypal_id is not None

    response = await client.post(f"/tickets/{ticket_id}/check-payment", headers={"Authorization": token})
    assert response.status_code == 400

    #response = await client.post(f"/tickets/{ticket_id}/check-payment", headers={"Authorization": token})
    #assert response.status_code == 204

    response = await client.get(f"/tickets", headers={"Authorization": token})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = await client.get(f"/tickets/{ticket_id}", headers={"Authorization": token})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ticket_verify(client: AsyncClient):
    user = await create_test_user()
    manager = await create_test_user(role=UserRole.MANAGER)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(
        name=f"Test event", description=f"test", category="test", location=location, city="test", manager=manager
    )
    plan = await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)
    ticket = await Ticket.create(amount=1, event_plan=plan, user=user)
    payment = await Payment.create(ticket=ticket, state=PaymentState.AWAITING_PAYMENT)

    response = await client.get(f"/tickets/{ticket.id}/validation-tokens", headers={"Authorization": token})
    assert response.status_code == 403

    response = await client.get(f"/tickets/{ticket.id+1}/validation-tokens", headers={"Authorization": token})
    assert response.status_code == 404

    await payment.update(state=PaymentState.DONE)

    response = await client.get(f"/tickets/{ticket.id}/validation-tokens", headers={"Authorization": token})
    assert response.status_code == 200
    jwt_tokens = response.json()
    assert len(jwt_tokens) == 1

    admin_user = await create_test_user(role=UserRole.ADMIN)
    admin_token = await create_session_token(admin_user)

    response = await client.post(f"/admin/tickets/validate", headers={"Authorization": admin_token}, json={
        "event_id": event.id,
        "ticket": jwt_tokens[0],
    })
    assert response.status_code == 200
    resp = response.json()
    assert resp["user"] == {
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    assert resp["plan"] == plan.to_json()

    response = await client.post(f"/admin/tickets/validate", headers={"Authorization": admin_token}, json={
        "event_id": event.id + 1,
        "ticket": jwt_tokens[0],
    })
    assert response.status_code == 400

    response = await client.post(f"/admin/tickets/validate", headers={"Authorization": admin_token}, json={
        "event_id": event.id,
        "ticket": "asdqwe",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unknown_plan(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.post("/tickets/request-payment", headers={"Authorization": token}, json={
        "event_id": 123,
        "plan_id": 123,
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unknown_ticket(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)

    response = await client.get("/tickets/123", headers={"Authorization": token})
    assert response.status_code == 404

    response = await client.get("/tickets/123/check-verification", headers={"Authorization": token})
    assert response.status_code == 404

    response = await client.post("/tickets/123/verify-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 404

    response = await client.post("/tickets/123/check-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_ticket(client: AsyncClient):
    user = await create_test_user()
    manager = await create_test_user(role=UserRole.MANAGER)
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(
        name=f"Test event", description=f"test", category="test", location=location, city="test", manager=manager
    )
    plan = await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)

    ticket = await Ticket.create(amount=1, event_plan=plan, user=user)
    await Payment.create(ticket=ticket, expires_at=datetime.now(UTC), state=PaymentState.AWAITING_PAYMENT)

    response = await client.delete(f"/tickets/{ticket.id+1}", headers={"Authorization": token})
    assert response.status_code == 404

    response = await client.delete(f"/tickets/{ticket.id}", headers={"Authorization": token})
    assert response.status_code == 204

    ticket = await Ticket.create(amount=1, event_plan=plan, user=user)
    await Payment.create(ticket=ticket, expires_at=datetime.now(UTC), state=PaymentState.DONE)

    response = await client.delete(f"/tickets/{ticket.id}", headers={"Authorization": token})
    assert response.status_code == 400


