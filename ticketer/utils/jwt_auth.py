from typing import Callable, Awaitable

from fastapi import Request, Depends

from ticketer.config import JWT_KEY
from ticketer.exceptions import UnauthorizedException, ForbiddenException
from ticketer.models import User, UserRole
from ticketer.models.session import AuthSession
from ticketer.utils.jwt import JWT


async def jwt_auth(request: Request) -> User:
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


def jwt_auth_role(role: UserRole) -> Callable[[User], Awaitable[User]]:
    async def auth_role(user: User = Depends(jwt_auth)) -> User:
        if user.role < role:
            raise ForbiddenException("Insufficient permissions.")

        return user

    return auth_role
