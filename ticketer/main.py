from pathlib import Path
from time import time

from aerich import Command
from bcrypt import gensalt, hashpw, checkpw
from fastapi import FastAPI, Request, Depends
from starlette.responses import JSONResponse
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from ticketer.config import OAUTH_GOOGLE_CLIENT_ID, OAUTH_GOOGLE_REDIRECT, JWT_KEY
from ticketer.exceptions import CustomBodyException
from ticketer.models import User, AuthSession, ExternalAuth, PaymentMethod, Event
from ticketer.schemas import LoginData, RegisterData, GoogleOAuthData, EditProfileData, AddPaymentMethodData
from ticketer.utils import is_valid_card
from ticketer.utils.google_oauth import authorize_google
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.turnstile import Turnstile

app = FastAPI()


@app.on_event("startup")
async def migrate_orm():
    migrations_dir = "data/migrations"

    command = Command({
        "connections": {"default": "sqlite://pr.db"},
        "apps": {"models": {"models": ["pr.models", "aerich.models"], "default_connection": "default"}},
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
    db_url="sqlite://pr.db",
    modules={"models": ["pr.models"]},
    generate_schemas=True,
)


@app.exception_handler(CustomBodyException)
async def custom_exception_handler(request: Request, exc: CustomBodyException):
    return JSONResponse(status_code=exc.code, content=exc.body)


@app.post("/auth/register")
async def register(data: RegisterData):
    if not await Turnstile.verify(data.captcha_key):
        raise CustomBodyException(code=400, body={"error_message": f"Failed to verify captcha!"})
    if await User.filter(email=data.email).exists():
        raise CustomBodyException(code=400, body={"error_message": f"User with this email already exists!"})

    password_hash = hashpw(data.password.encode("utf8"), gensalt()).decode()
    user = await User.create(
        email=data.email, password=password_hash, first_name=data.first_name, last_name=data.last_name
    )
    session = await AuthSession.create(user=user)

    return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp())}


@app.post("/auth/login")
async def login(data: LoginData):
    if not await Turnstile.verify(data.captcha_key):
        raise CustomBodyException(code=400, body={"error_message": f"Failed to verify captcha!"})
    if (user := await User.get_or_none(email=data.email)) is None:
        raise CustomBodyException(code=400, body={"error_message": f"Wrong email or password!"})

    if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
        raise CustomBodyException(code=400, body={"error_message": f"Wrong email or password!"})

    session = await AuthSession.create(user=user)
    return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp())}


@app.get("/auth/google")
async def google_auth_link():
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline"
    }


@app.post("/auth/google/connect")
async def google_auth_connect_link(user: User = Depends(jwt_auth)):
    if await ExternalAuth.filter(user=user).exists():
        raise CustomBodyException(code=400, body={"error_message": "You already have connected google account."})

    state = JWT.encode({"user_id": user.id, "type": "google-connect"}, JWT_KEY, expires_in=180)
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline&state={state}"
    }


@app.post("/auth/google/callback")
async def google_auth_callback(data: GoogleOAuthData):
    state = JWT.decode(data.state or "", JWT_KEY)
    if state.get("type") != "google-connect":
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
        # Connect external service to user account
        if await ExternalAuth.filter(user__id=state["user_id"]).exists():
            raise CustomBodyException(code=400, body={"error_message": "You already have connected google account."})

        await ExternalAuth.create(
            user=user,
            service="google",
            service_id=data["id"],
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=int(time() + token_data["expires_in"]),
        )
    elif state is not None and eauth is not None:
        # Trying to connect external account that is already connected, ERROR!!
        raise CustomBodyException(code=400, body={"error_message": "This account is already connected."})
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
    if require_password and not data.password:
        raise CustomBodyException(code=400, body={"error_message": "You need to enter your password."})
    elif require_password and data.password:
        if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
            raise CustomBodyException(code=400, body={"error_message": f"Wrong password!"})

    # TODO: mfa
    j_data = data.model_dump(exclude_defaults=True, exclude={"mfa_key", "password", "new_password"})
    if data.new_password is not None:
        j_data["password"] = hashpw(data.new_password.encode("utf8"), gensalt()).decode()

    if j_data:
        await user.update(**j_data)

    return get_user_info(user)


@app.get("/users/me/billing")
async def get_payment_methods(user: User = Depends(jwt_auth)):
    payment_methods = await PaymentMethod.filter(user=user)

    return [{
        "type": method.type,
        "card_number": method.card_number,
        "expiration_date": method.expiration_date,
        "expired": method.expired(),
    } for method in payment_methods]


@app.post("/users/me/billing")
async def add_payment_method(data: AddPaymentMethodData, user: User = Depends(jwt_auth)):
    if not is_valid_card(data.card_number, data.expiration_date):
        raise CustomBodyException(code=400, body={"error_message": f"Card details you provided are invalid."})

    await PaymentMethod.get_or_create(user=user, card_number=data.card_number, defaults={
        "expiration_date": data.expiration_date,
    })

    return {
        "type": data.type,
        "card_number": data.card_number,
        "expiration_date": data.expiration_date,
        "expired": False,
    }


@app.delete("/users/me/billing/{card_number}", status_code=204)
async def delete_payment_method(card_number: str, user: User = Depends(jwt_auth)):
    await PaymentMethod.filter(user=user, card_number=card_number).delete()


@app.get("/events")
async def get_events(page: int = 1, with_plans: bool = False):
    events = await Event.filter().limit(10).offset((page-1) * 10).select_related("location")

    result = []
    for event in events:
        result.append({
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": {
                "name": event.location.name,
                "longitude": event.location.longitude,
                "latitude": event.location.latitude,
            },
        })
        if with_plans:
            plans = await event.plans.all()
            result[-1]["plans"] = [{
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "max_tickets": plan.max_tickets,
            } for plan in plans]

    return result
