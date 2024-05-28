import pytest
from httpx import AsyncClient

from tests import create_test_user, create_session_token
from ticketer.models import Location, Event, EventPlan, PaymentState, Ticket, Payment, UserRole
from ticketer.utils.paypal import PayPal


@pytest.mark.asyncio
async def test_full_purchase(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(name=f"Test event", description=f"test", category="test", location=location, city="test")
    plan = await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)

    response = await client.post("/tickets/request-payment", headers={"Authorization": token}, json={
        "event_id": event.id,
        "plan_id": plan.id,
    })
    assert response.status_code == 200
    ticket_id = response.json()["ticket_id"]

    response = await client.get(f"/tickets/{ticket_id}/check-verification", headers={"Authorization": token})
    assert response.status_code == 200
    assert response.json()["payment_state"] == PaymentState.AWAITING_VERIFICATION

    response = await client.post(f"/tickets/{ticket_id}/verify-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 204
    response = await client.post(f"/tickets/{ticket_id}/verify-payment", headers={"Authorization": token}, json={})
    assert response.status_code == 400

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


@pytest.mark.asyncio
async def test_ticket_verify(client: AsyncClient):
    user = await create_test_user()
    token = await create_session_token(user)
    location = await Location.create(name="test", longitude=0, latitude=0)
    event = await Event.create(name=f"Test event", description=f"test", category="test", location=location, city="test")
    plan = await EventPlan.create(name="test", price=100, max_tickets=1000, event=event)
    ticket = await Ticket.create(amount=1, event_plan=plan, user=user)
    payment = await Payment.create(ticket=ticket, state=PaymentState.AWAITING_PAYMENT)

    response = await client.get(f"/tickets/{ticket.id}/validation-tokens", headers={"Authorization": token})
    assert response.status_code == 403

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

