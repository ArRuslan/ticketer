from datetime import timedelta, datetime, UTC

from fastapi import APIRouter
from fastapi import Depends

from ticketer import config
from ticketer.config import fcm
from ticketer.errors import Errors
from ticketer.models import User, Event, Ticket, Payment, PaymentState, EventPlan, UserDevice, UserRole
from ticketer.response_schemas import TicketData, BuyTicketVerifiedData, BuyTicketRespData, PendingConfirmationData
from ticketer.schemas import BuyTicketData, VerifyPaymentData
from ticketer.utils.cache import RedisCache
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth, jwt_auth_role
from ticketer.utils.mfa import MFA
from ticketer.utils.paypal import PayPal

router = APIRouter(prefix="/tickets")


@router.get("", response_model=list[TicketData])
async def get_user_tickets(user: User = Depends(jwt_auth)):
    cached = await RedisCache.get("tickets", user.id)
    if cached is not None:
        return cached

    tickets = await Ticket.filter(user=user).select_related("event_plan", "event_plan__event")\
        .order_by("event_plan__event__start_time")

    result = [{
        "id": ticket.id,
        "amount": ticket.amount,
        "plan": ticket.event_plan.to_json(),
        "event": ticket.event_plan.event.to_json(),
        "can_be_cancelled": await ticket.can_be_cancelled(),
    } for ticket in tickets]

    await RedisCache.put("tickets", result, user.id, expires_in=300)
    return result


@router.get("{ticket_id}", response_model=TicketData)
async def get_ticket(ticket_id: int, user: User = Depends(jwt_auth)):
    cached = await RedisCache.get("tickets_one", user.id, ticket_id)
    if cached is not None:
        return cached

    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan", "event_plan__event")
    if ticket is None:
        raise Errors.UNKNOWN_TICKET

    result = {
        "id": ticket.id,
        "amount": ticket.amount,
        "plan": ticket.event_plan.to_json(),
        "event": ticket.event_plan.event.to_json(),
        "can_be_cancelled": await ticket.can_be_cancelled(),
    }

    await RedisCache.put("tickets_one", result, user.id, ticket_id, expires_in=300)
    return result


@router.post("/request-payment", response_model=BuyTicketRespData)
async def request_ticket(data: BuyTicketData, user: User = Depends(jwt_auth_role(exact=UserRole.USER))):
    if (event_plan := await EventPlan.get_or_none(id=data.plan_id, event__id=data.event_id)) is None:
        raise Errors.UNKNOWN_PLAN
    tickets_available = event_plan.max_tickets - await Ticket.filter(event_plan=event_plan).count()
    if tickets_available < data.amount:
        raise Errors.TICKETS_NOT_AVAILABLE.format(data.amount)

    ticket = await Ticket.create(user=user, event_plan=event_plan, amount=data.amount)
    payment = await Payment.create(ticket=ticket)
    await RedisCache.delete("tickets", user.id)

    total_price = event_plan.price * data.amount

    async for device in UserDevice.filter(user=user):
        if not isinstance(event_plan.event, Event):
            await event_plan.fetch_related("event")

        await fcm.send_notification(
            "Payment Verification",
            f"Payment verification for ${total_price:.2f} is needed to buy a ticket",
            device_token=device.device_token,
        )
        #await fcm.send_data(
        #    ticket_id=ticket.id,
        #    payment_id=payment.id,
        #    amount=data.amount,
        #    event=event_plan.event.to_json(),
        #    expires_at=int(payment.expires_at.timestamp()),
        #    device_token=device.device_token,
        #)

    return {
        "ticket_id": ticket.id,
        "total_price": total_price,
        "expires_at": int(payment.expires_at.timestamp())
    }


@router.get("/pending-confirmations", response_model=list[PendingConfirmationData])
async def get_pending_confirmations(user: User = Depends(jwt_auth)):
    pending = await Payment.filter(state=PaymentState.AWAITING_VERIFICATION, ticket__user=user).select_related("ticket")

    return [{
        "ticket_id": payment.ticket.id,
        "expires_at": int(payment.expires_at.timestamp()),
    } for payment in pending]


@router.get("/{ticket_id}/check-verification", response_model=BuyTicketVerifiedData)
async def check_ticket_verification(ticket_id: int, user: User = Depends(jwt_auth)):
    if (payment := await Payment.get_or_none(ticket__id=ticket_id, ticket__user=user)) is None:
        raise Errors.UNKNOWN_TICKET

    return {
        "ticket_id": ticket_id,
        "payment_state": payment.state,
        "expires_at": int(payment.expires_at.timestamp()),
        "paypal_id": payment.paypal_id,
    }


@router.post("/{ticket_id}/verify-payment", status_code=204)
async def verify_ticket_payment(ticket_id: int, data: VerifyPaymentData, user: User = Depends(jwt_auth)):
    if (payment := await Payment.get_or_none(ticket__id=ticket_id, ticket__user=user)) is None:
        raise Errors.UNKNOWN_TICKET
    if payment.state != PaymentState.AWAITING_VERIFICATION:
        raise Errors.TICKET_ALREADY_VERIFIED

    if user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise Errors.WRONG_MFA_CODE

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
        raise Errors.UNKNOWN_TICKET

    if payment.state == PaymentState.DONE:
        return
    if payment.paypal_id is None or not await PayPal.check(payment.paypal_id):
        raise Errors.PAYMENT_NOT_RECEIVED

    await payment.update(state=PaymentState.DONE)
    await RedisCache.delete("tickets_one", user.id, ticket_id)


@router.get("/{ticket_id}/validation-tokens", response_model=list[str])
async def create_ticket_token(ticket_id: int, user: User = Depends(jwt_auth)):
    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan", "event_plan__event")
    if ticket is None:
        raise Errors.UNKNOWN_TICKET
    if (payment := await Payment.get_or_none(ticket=ticket)) is None or payment.state != PaymentState.DONE:
        raise Errors.PAYMENT_NOT_RECEIVED_TOKEN

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
        raise Errors.UNKNOWN_TICKET

    payment = await Payment.get_or_none(ticket=ticket)

    if (ticket.event_plan.event.start_time.replace(tzinfo=UTC) - datetime.now(UTC)) > timedelta(hours=3) and \
            payment is not None and payment.state == PaymentState.DONE:
        raise Errors.TICKET_CANNOT_CANCEL

    await ticket.delete()
    await RedisCache.delete("tickets", user.id)
