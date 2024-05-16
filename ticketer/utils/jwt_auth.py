from fastapi import Request

from ticketer.config import JWT_KEY
from ticketer.exceptions import UnauthorizedException
from ticketer.models.session import AuthSession
from ticketer.utils.jwt import JWT


async def jwt_auth(request: Request):
    token = request.headers.get("authorization")
    if not token or (data := JWT.decode(token, JWT_KEY)) is None:
        raise UnauthorizedException("Invalid token.")
    if "user" not in data or "session" not in data or "token" not in data:
        raise UnauthorizedException("Invalid token.")

    sess = await AuthSession.get_or_none(id=data["session"], user__id=data["user"], token=data["token"]) \
        .select_related("user")
    if sess is None:
        raise UnauthorizedException("Invalid token.")

    return sess.user
