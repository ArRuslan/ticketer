from datetime import datetime, UTC

from fastapi import FastAPI, Request, Depends
from starlette.responses import JSONResponse

from ticketer.exceptions import CustomBodyException, NotFoundException, ForbiddenException
from ticketer.models import User, UserRole, Location, Event, EventPlan
from ticketer.schemas import AdminUserSearchData, AddEventData, EditEventData
from ticketer.utils.jwt_auth import jwt_auth_role

app = FastAPI()


# noinspection PyUnusedLocal
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
    if (user_to_ban := await User.get_or_none(id=user_id)) is None:
        raise NotFoundException("Unknown user.")
    if user_to_ban.role >= user.role:
        raise ForbiddenException("You cannot ban this user.")

    await user_to_ban.update(banned=True)


@app.post("/users/{user_id}/unban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user_to_unban := await User.get_or_none(id=user_id)) is None:
        raise NotFoundException("Unknown user.")
    if user_to_unban.role >= user.role:
        raise ForbiddenException("You cannot unban this user.")

    await user_to_unban.update(banned=False)


# noinspection PyUnusedLocal
@app.post("/events")
async def add_event(data: AddEventData, user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    if (location := await Location.get_or_none(id=data.location_id)) is None:
        raise NotFoundException("Unknown location.")

    create_args = data.model_dump(exclude={"location_id", "plans", "start_time", "end_time", "image"})
    create_args["location"] = location
    create_args["start_time"] = datetime.fromtimestamp(data.start_time, UTC)
    create_args["end_time"] = datetime.fromtimestamp(data.end_time, UTC)

    event = await Event.create(**create_args)
    for plan in data.plans:
        await EventPlan.create(**plan.model_dump(), event=event)

    return {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "category": event.category,
        "start_time": int(event.start_time.timestamp()),
        "end_time": int(event.end_time.timestamp()),
        "location": {
            "name": location.name,
            "longitude": location.longitude,
            "latitude": location.latitude,
        },
    }


# noinspection PyUnusedLocal
@app.patch("/events/{event_id}")
async def edit_event(event_id: int, data: EditEventData, user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    if (event := await Event.get_or_none(id=event_id)) is None:
        raise NotFoundException("Unknown event.")

    location = None
    if data.location_id is not None and (location := await Location.get_or_none(id=data.location_id)) is None:
        raise NotFoundException("Unknown location.")

    args = data.model_dump(exclude={"location_id", "plans", "start_time", "end_time", "image"})
    if data.start_time is not None:
        args["start_time"] = datetime.fromtimestamp(data.start_time, UTC)
    if data.end_time is not None:
        args["end_time"] = datetime.fromtimestamp(data.end_time, UTC)
    if location is not None:
        args["location"] = location

    await event.update(**args)
    if data.plans is not None:
        await EventPlan.filter(event=event).delete()
        for plan in data.plans:
            await EventPlan.create(**plan.model_dump(), event=event)

    return {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "category": event.category,
        "start_time": int(event.start_time.timestamp()),
        "end_time": int(event.end_time.timestamp()),
        "location": {
            "name": location.name,
            "longitude": location.longitude,
            "latitude": location.latitude,
        },
    }
