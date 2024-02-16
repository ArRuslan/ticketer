from fastapi import Request

from pr.config import JWT_KEY
from pr.exceptions import UnauthorizedException
from pr.models.session import AuthSession
from pr.utils.jwt import JWT


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
