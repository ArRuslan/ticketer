from datetime import timedelta, datetime, UTC
from pathlib import Path
from time import time
from typing import Literal

from aerich import Command
from bcrypt import gensalt, hashpw, checkpw
from fastapi import FastAPI, Request, Depends
from starlette.responses import JSONResponse
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from ticketer import config, admin
from ticketer.exceptions import CustomBodyException, BadRequestException, NotFoundException, ForbiddenException
from ticketer.models import User, AuthSession, ExternalAuth, PaymentMethod, Event, Ticket
from ticketer.schemas import LoginData, RegisterData, GoogleOAuthData, EditProfileData, AddPaymentMethodData, \
    BuyTicketData, EventSearchData
from ticketer.utils import is_valid_card
from ticketer.utils.google_oauth import authorize_google
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.mfa import MFA
from ticketer.utils.turnstile import Turnstile

app = FastAPI()
app.mount("/admin", admin.app)


@app.on_event("startup")
async def migrate_orm():  # pragma: no cover
    if config.DB_CONNECTION_STRING == "sqlite://:memory:":
        return
    migrations_dir = "data/migrations"

    command = Command({
        "connections": {"default": config.DB_CONNECTION_STRING},
        "apps": {"models": {"models": ["ticketer.models", "aerich.models"], "default_connection": "default"}},
    }, location=migrations_dir)
    await command.init()
    if Path(migrations_dir).exists():
        await command.migrate()
        await command.upgrade(True)
    else:
        await command.init_db(True)
    await Tortoise.close_connections()


register_tortoise(
    app,
    db_url=config.DB_CONNECTION_STRING,
    modules={"models": ["ticketer.models"]},
    generate_schemas=True,
)


# noinspection PyUnusedLocal
@app.exception_handler(CustomBodyException)
async def custom_exception_handler(request: Request, exc: CustomBodyException):
    return JSONResponse(status_code=exc.code, content=exc.body)


@app.post("/auth/register")
async def register(data: RegisterData):
    if not await Turnstile.verify(data.captcha_key):
        raise BadRequestException("Failed to verify captcha!")
    if await User.filter(email=data.email).exists():
        raise BadRequestException("User with this email already exists!")

    password_hash = hashpw(data.password.encode("utf8"), gensalt()).decode()
    user = await User.create(
        email=data.email, password=password_hash, first_name=data.first_name, last_name=data.last_name
    )
    session = await AuthSession.create(user=user)

    return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp())}


@app.post("/auth/login")
async def login(data: LoginData):
    if not await Turnstile.verify(data.captcha_key):
        raise BadRequestException("Failed to verify captcha!")
    if (user := await User.get_or_none(email=data.email)) is None:
        raise BadRequestException("Wrong email or password!")

    if user.banned:
        raise ForbiddenException("Your account is banned!")

    if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
        raise BadRequestException("Wrong email or password!")

    if user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")

    session = await AuthSession.create(user=user)
    return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp())}


@app.get("/auth/google")
async def google_auth_link():
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={config.OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={config.OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline"
    }


@app.post("/auth/google/connect")
async def google_auth_connect_link(user: User = Depends(jwt_auth)):
    if await ExternalAuth.filter(user=user).exists():
        raise BadRequestException("You already have connected google account.")

    state = JWT.encode({"user_id": user.id, "type": "google-connect"}, config.JWT_KEY, expires_in=180)
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={config.OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={config.OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline&state={state}"
    }


@app.post("/auth/google/callback")
async def google_auth_callback(data: GoogleOAuthData):
    state = JWT.decode(data.state or "", config.JWT_KEY)
    if state is not None and state.get("type") != "google-connect":
        state = None

    data, token_data = await authorize_google(data.code)
    eauth = await ExternalAuth.get_or_none(service="google", service_id=data["id"]).select_related("user")
    if eauth is not None:
        await eauth.update(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=int(time() + token_data["expires_in"]),
        )

    user = None
    if state is not None and eauth is None:
        # Connect external service to a user account
        if await ExternalAuth.filter(user__id=state["user_id"]).exists():
            raise BadRequestException("You already have connected google account.")

        await ExternalAuth.create(
            user=await User.get(id=state["user_id"]),
            service="google",
            service_id=data["id"],
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=int(time() + token_data["expires_in"]),
        )
    elif state is not None and eauth is not None:
        # Trying to connect an external account that is already connected, ERROR!!
        raise BadRequestException("This account is already connected.")
    elif state is None and eauth is None:
        # Register new user
        user = await User.create(first_name=data["given_name"], last_name=data["family_name"])
        await ExternalAuth.create(
            user=user,
            service="google",
            service_id=data["id"],
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=int(time() + token_data["expires_in"]),
        )
    elif state is None and eauth is not None:
        # Authorize user
        user = eauth.user
    else:
        raise Exception("Unreachable")

    if user is None:
        return {"token": None, "expires_at": 0, "connect": True}
    else:
        session = await AuthSession.create(user=user)
        return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp()), "connect": False}


@app.get("/users/me")
async def get_user_info(user: User = Depends(jwt_auth)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "mfa_enabled": user.mfa_key is not None,
    }


@app.patch("/users/me")
async def edit_user_info(data: EditProfileData, user: User = Depends(jwt_auth)):
    require_password = data.mfa_key is not None or data.new_password is not None or data.email is not None \
                       or data.phone_number is not None
    if data.mfa_key and user.mfa_key is not None:
        raise BadRequestException("Two-factory authentication is already enabled.")
    elif data.mfa_key is None and user.mfa_key is None:
        raise BadRequestException("Two-factory authentication is already disabled.")

    if require_password and not data.password:
        raise BadRequestException("You need to enter your password.")
    elif require_password and data.password:
        if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
            raise BadRequestException("Wrong password.")

    if data.mfa_key:
        mfa = MFA(data.mfa_key)
        if not mfa.valid:
            raise BadRequestException("Invalid two-factor authentication key.")
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")
    elif data.mfa_key is None and user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")

    # TODO: check if phone number is already used
    j_data = data.model_dump(exclude_defaults=True, exclude={"password", "new_password"})
    if data.new_password is not None:
        j_data["password"] = hashpw(data.new_password.encode("utf8"), gensalt()).decode()

    if j_data:
        await user.update(**j_data)

    return await get_user_info(user)


@app.get("/users/me/payment")
async def get_payment_methods(user: User = Depends(jwt_auth)):
    payment_methods = await PaymentMethod.filter(user=user)

    return [{
        "type": method.type,
        "card_number": method.card_number,
        "expiration_date": method.expiration_date,
        "expired": method.expired(),
    } for method in payment_methods]


@app.post("/users/me/payment")
async def add_payment_method(data: AddPaymentMethodData, user: User = Depends(jwt_auth)):
    if not is_valid_card(data.card_number, data.expiration_date):
        raise BadRequestException("Card details you provided are invalid.")

    await PaymentMethod.get_or_create(user=user, type=data.type, card_number=data.card_number, defaults={
        "expiration_date": data.expiration_date,
    })

    return {
        "type": data.type,
        "card_number": data.card_number,
        "expiration_date": data.expiration_date,
        "expired": False,
    }


@app.delete("/users/me/payment/{card_number}", status_code=204)
async def delete_payment_method(card_number: str, user: User = Depends(jwt_auth)):
    await PaymentMethod.filter(user=user, card_number=card_number).delete()


# TODO: add searching and sorting by price
@app.post("/events/search")
async def search_events(data: EventSearchData, sort_by: Literal["name", "category", "start_time"] | None = None,
                     sort_direction: Literal["asc", "desc"] = "asc", results_per_page: int = 10, page: int = 1,
                     with_plans: bool = False):
    page = max(page, 1)
    results_per_page = min(results_per_page, 50)
    results_per_page = max(results_per_page, 5)

    query_args = data.model_dump(exclude_defaults=True, exclude={"time_min", "time_max"})
    if data.time_max:
        query_args["start_time__lte"] = datetime.fromtimestamp(data.time_max, UTC)
    if data.time_min:
        query_args["start_time__gte"] = datetime.fromtimestamp(data.time_min, UTC)
    if data.name:
        del query_args["name"]
        query_args["name__contains"] = data.name

    events_query = Event.filter(**query_args).limit(results_per_page).offset((page - 1) * 10).select_related("location")
    if sort_by is not None:
        if sort_direction == "desc":
            sort_by = f"-{sort_by}"
        events_query = events_query.order_by(sort_by)

    result = []
    for event in await events_query:
        result.append(event.to_json())
        if with_plans:
            plans = await event.plans.all()
            result[-1]["plans"] = [{
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "max_tickets": plan.max_tickets,
            } for plan in plans]

    return result


@app.get("/events/{event_id}")
async def get_events(event_id: int, with_plans: bool = False):
    event = await Event.get_or_none(id=event_id).select_related("location")

    result = event.to_json()
    if with_plans:
        result["plans"] = [{
            "id": plan.id,
            "name": plan.name,
            "price": plan.price,
            "max_tickets": plan.max_tickets,
        } for plan in await event.plans.all()]

    return result


@app.get("/tickets")
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


@app.post("/tickets")
async def buy_ticket(data: BuyTicketData, user: User = Depends(jwt_auth)):
    # TODO: implement
    raise NotImplementedError


@app.get("/tickets/{ticket_id}/validation-tokens")
async def view_ticket(ticket_id: int, user: User = Depends(jwt_auth)):
    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan", "event_plan__event")
    if ticket is None:
        raise NotFoundException("Unknown ticket.")

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
        event.end_time.timestamp()
    ) for num in range(ticket.amount)]


@app.delete("/tickets/{ticket_id}", status_code=204)
async def cancel_user_ticket(ticket_id: int, user: User = Depends(jwt_auth)):
    ticket = await Ticket.get_or_none(id=ticket_id, user=user).select_related("event_plan__event")
    if ticket is None:
        raise NotFoundException("Unknown ticket.")

    if (ticket.event_plan.event.start_time - datetime.now()) > timedelta(hours=3):
        raise BadRequestException("This ticket cannot be cancelled.")

    await ticket.delete()
