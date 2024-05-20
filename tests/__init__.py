import json
from time import time

from bcrypt import hashpw, gensalt
from httpx import Request, Response

from ticketer.models import User, AuthSession, UserRole


async def create_test_user(email: str | None = None, password: str | None = None,
                           role: UserRole = UserRole.USER) -> User:
    email = email or f"test.{time()}@ticketer.com"
    password = (password or "123456789").encode("utf8")

    password_hash = hashpw(password, gensalt(rounds=4)).decode()

    return await User.create(
        email=email, password=password_hash, first_name="Test", last_name="Test", role=role
    )


async def create_session_token(user: User) -> str:
    session = await AuthSession.create(user=user)
    return session.to_jwt()


def google_oauth_token_exchange(code: str, access_token: str):
    def _google_oauth_token_exchange(request: Request) -> Response:
        params = json.loads(request.content.decode("utf8"))
        if params["code"] != code:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={
            "access_token": access_token, "refresh_token": access_token[::-1], "expires_in": 3600
        })

    return _google_oauth_token_exchange


def google_oauth_user_info(access_token: str):
    def _google_oauth_token_exchange(request: Request) -> Response:
        token = request.headers["Authorization"].split(" ")[1].strip()
        if token != access_token:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={
            "id": str(int(time()*1000)),
            "email": f"test.{time()}@gmail.com",
            "given_name": "Test",
            "family_name": "Test",
        })

    return _google_oauth_token_exchange

