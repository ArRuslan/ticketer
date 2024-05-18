from fastapi import FastAPI, Request, Depends
from starlette.responses import JSONResponse

from ticketer.exceptions import CustomBodyException
from ticketer.models import User, UserRole
from ticketer.schemas import AdminUserSearchData
from ticketer.utils.jwt_auth import jwt_auth_role

app = FastAPI()


@app.exception_handler(CustomBodyException)
async def custom_exception_handler(request: Request, exc: CustomBodyException):
    return JSONResponse(status_code=exc.code, content=exc.body)


@app.post("/users")
async def search_users(data: AdminUserSearchData, user: User = Depends(jwt_auth_role(UserRole.ADMIN)),
                       limit: int = 50, page: int = 1):
    query_args = data.model_dump(exclude_defaults=True)
    query_args["role__lt"] = user.role

    users = await User.filter(**query_args).limit(limit).offset((page - 1) * 10)

    return [{
        "id": user.id,
        "email": user.email,
        "has_password": user.password is not None,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar_id": user.avatar_id,
        "phone_number": user.phone_number,
        "mfa_enabled": user.mfa_key is not None,
        "banned": user.banned,
        "role": user.role,
    } for user in users]


@app.post("/users/{user_id}/ban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    await User.filter(id=user_id).update(banned=True)


@app.post("/users/{user_id}/unban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    await User.filter(id=user_id).update(banned=False)

