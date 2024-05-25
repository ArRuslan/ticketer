from time import time

from bcrypt import hashpw, gensalt, checkpw
from fastapi import APIRouter, Depends

from ticketer import config
from ticketer.exceptions import ForbiddenException, BadRequestException
from ticketer.models import User, AuthSession, ExternalAuth
from ticketer.schemas import LoginData, RegisterData, GoogleOAuthData
from ticketer.utils.google_oauth import authorize_google
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.mfa import MFA
from ticketer.utils.turnstile import Turnstile

router = APIRouter(prefix="/auth")


@router.post("/register")
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


@router.post("/login")
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


@router.get("/google")
async def google_auth_link():
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={config.OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={config.OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline"
    }


@router.post("/google/connect")
async def google_auth_connect_link(user: User = Depends(jwt_auth)):
    if await ExternalAuth.filter(user=user).exists():
        raise BadRequestException("You already have connected google account.")

    state = JWT.encode({"user_id": user.id, "type": "google-connect"}, config.JWT_KEY, expires_in=180)
    return {
        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={config.OAUTH_GOOGLE_CLIENT_ID}"
               f"&redirect_uri={config.OAUTH_GOOGLE_REDIRECT}&scope=profile%20email&access_type=offline&state={state}"
    }


@router.post("/google/callback")
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