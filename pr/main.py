from pathlib import Path

from aerich import Command
from bcrypt import gensalt, hashpw, checkpw
from fastapi import FastAPI, Request, Depends
from httpx import AsyncClient
from starlette.responses import JSONResponse
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from pr.config import OAUTH_GOOGLE_CLIENT_ID, OAUTH_GOOGLE_REDIRECT, OAUTH_GOOGLE_CLIENT_SECRET
from pr.exceptions import CustomBodyException
from pr.models import User, AuthSession
from pr.schemas import LoginData, RegisterData
from pr.utils.jwt_auth import jwt_auth
from pr.utils.turnstile import Turnstile

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


@app.get("/auth/google/callback")
async def google_auth_callback(code: str):
    data = {
        "code": code,
        "client_id": OAUTH_GOOGLE_CLIENT_ID,
        "client_secret": OAUTH_GOOGLE_CLIENT_SECRET,
        "redirect_uri": OAUTH_GOOGLE_REDIRECT,
        "grant_type": "authorization_code",
    }
    async with AsyncClient() as client:
        resp = await client.post("https://accounts.google.com/o/oauth2/token", json=data)
        if "error" in resp.json():
            raise CustomBodyException(code=400, body={"error_message": f"Error: {resp.json()['error']}"})
        # {'access_token': ..., 'expires_in': ..., 'refresh_token': ...}
        token = resp.json()["access_token"]

        info_resp = await client.get("https://www.googleapis.com/oauth2/v1/userinfo",
                                     headers={"Authorization": f"Bearer {token}"})
        data = info_resp.json()

    user, _ = await User.get_or_create(email=data["email"], defaults={
        "first_name": data["given_name"],
        "last_name": data["family_name"],
    })
    # google_auth, created = await GoogleAuth.get_or_create()
    session = await AuthSession.create(user=user)

    return {"token": session.to_jwt(), "expires_at": int(session.expires.timestamp())}


@app.get("/users/self")
async def get_user_info(user: User = Depends(jwt_auth)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
