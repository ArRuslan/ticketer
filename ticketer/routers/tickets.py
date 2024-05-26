from datetime import timedelta, datetime

from aiofcm import Message
from fastapi import APIRouter
from fastapi import Depends

from ticketer import config
from ticketer.config import fcm
from ticketer.exceptions import BadRequestException, NotFoundException, ForbiddenException
from ticketer.models import User, Event, Ticket, Payment, PaymentState, \
    EventPlan, UserDevice
from ticketer.schemas import BuyTicketData, VerifyPaymentData
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.mfa import MFA
from ticketer.utils.paypal import PayPal

router = APIRouter(prefix="/tickets")


@router.get("")
async def get_user_tickets(user: User = Depends(jwt_auth)):
    # TODO: filter by start/end times (not-started, started, ended)
    tickets = await Ticket.filter(user=user).select_related("event_plan", "event_plan__event")

    return [{
        "id": ticket.id,
        "amount": ticket.amount,
        "plan": ticket.event_plan.to_json(),
        "event": ticket.event_plan.event.to_json(),
        "can_be_cancelled": (ticket.event_plan.event.start_time - datetime.now()) > timedelta(hours=3)
    } for ticket in tickets]


@router.post("/request-payment")
async def request_ticket(data: BuyTicketData, user: User = Depends(jwt_auth)):
    if (event_plan := await EventPlan.get_or_none(id=data.plan_id, event__id=data.event_id)) is None:
        raise NotFoundException("Unknown event plan.")
    tickets_available = event_plan.max_tickets - await Ticket.filter(event_plan=event_plan).count()
    if tickets_available < data.amount:
        raise BadRequestException(f"{data.amount} tickets not available. Try lowering tickets amount.")

    ticket = await Ticket.create(user=user, event_plan=event_plan, amount=data.amount)
    payment = await Payment.create(ticket=ticket)

    async for device in UserDevice.filter(user=user):
        if not isinstance(event_plan.event, Event):
            await event_plan.fetch_related("event")

        await fcm.send_message(Message(
            device_token=device.device_token,
            notification={
                "title": "Payment Verification",
                "body": "Payment verification is needed to buy a ticket",
                "sound": "default",
            },
            data={
                "ticket_id": ticket.id,
                "payment_id": payment.id,
                "amount": data.amount,
                "event": event_plan.event.to_json(),
                "expires_at": int(payment.expires_at.timestamp())
            },
            priority="high",
        ))

    return {
        "ticket_id": ticket.id,
        "total_price": event_plan.price * data.amount,
        "expires_at": int(payment.expires_at.timestamp())
    }


@router.get("/{ticket_id}/check-verification")
async def check_ticket_verification(ticket_id: int, user: User = Depends(jwt_auth)):
    if (payment := await Payment.get_or_none(ticket__id=ticket_id, ticket__user=user)) is None:
        raise NotFoundException("Unknown ticket.")

    return {
        "ticket_id": ticket_id,
        "payment_state": payment.state,
        "expires_at": int(payment.expires_at.timestamp()),
        "paypal_id": payment.paypal_id,
    }


@router.post("/{ticket_id}/verify-payment", status_code=204)
async def verify_ticket_payment(ticket_id: int, data: VerifyPaymentData, user: User = Depends(jwt_auth)):
    if (payment := await Payment.get_or_none(ticket__id=ticket_id, ticket__user=user)) is None:
        raise NotFoundException("Unknown ticket.")
    if payment.state != PaymentState.AWAITING_VERIFICATION:
        raise BadRequestException("Already verified.")

    if user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")

    await payment.fetch_related("ticket", "ticket__event_plan")
    ticket = payment.ticket
    event_plan = ticket.event_plan

    await payment.update(
        state=PaymentState.AWAITING_PAYMENT,
        paypal_id=await PayPal.create(event_plan.price * ticket.amount)
    )


@router.post("/{ticket_id}/check-payment", status_code=204)
async def ticket_payment_callback(ticket_id: int, user: User = Depends(jwt_auth)):
    if (payment := await Payment.get_or_none(ticket__id=ticket_id, ticket__user=user)) is None:
        raise NotFoundException("Unknown ticket.")

    if payment.state == PaymentState.DONE:
        return
    if payment.paypal_id is None or not await PayPal.check(payment.paypal_id):
        raise BadRequestException("Payment not received yet.")

    await payment.update(state=PaymentState.DONE)


@router.get("/{ticket_id}/validation-tokens")
async def create_ticket_token(ticket_id: int, user: User = Depends(jwt_auth)):
    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan", "event_plan__event")
    if ticket is None:
        raise NotFoundException("Unknown ticket.")
    if (payment := await Payment.get_or_none(ticket=ticket)) is None or payment.state != PaymentState.DONE:
        raise ForbiddenException("Payment is not received for this ticket.")

    plan = ticket.event_plan
    event = plan.event

    return [JWT.encode(
        {
            "user_id": user.id,
            "ticket_id": ticket.id,
            "plan_id": plan.id,
            "event_id": event.id,
            "ticket_num": num,
        },
        config.JWT_KEY,
        (event.end_time or (event.start_time + timedelta(hours=4))).timestamp()
    ) for num in range(ticket.amount)]


@router.delete("/{ticket_id}", status_code=204)
async def cancel_user_ticket(ticket_id: int, user: User = Depends(jwt_auth)):
    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan__event")
    if ticket is None:
        raise NotFoundException("Unknown ticket.")

    payment = await Payment.get_or_none(ticket=ticket)

    if (ticket.event_plan.event.start_time - datetime.now()) > timedelta(hours=3) and payment is not None and \
            payment.state == PaymentState.DONE:
        raise BadRequestException("This ticket cannot be cancelled.")

    await ticket.delete()
