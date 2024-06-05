from datetime import datetime, UTC
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends
from pyvips import Image

from ticketer import config
from ticketer.config import S3
from ticketer.errors import Errors
from ticketer.models import User, UserRole, Location, Event, EventPlan
from ticketer.response_schemas import AdminUserData, EventData, AdminTicketValidationData
from ticketer.schemas import AdminUserSearchData, AddEventData, EditEventData, TicketValidationData, AdminUserEditData
from ticketer.utils import open_image_b64, upload_image_or_not
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth_role

router = APIRouter(prefix="/admin")


@router.post("/users", response_model=list[AdminUserData])
async def search_users(data: AdminUserSearchData, user: User = Depends(jwt_auth_role(UserRole.ADMIN)),
                       limit: int = 50, page: int = 1):
    query_args = data.model_dump(exclude_defaults=True)
    query_args["role__lt"] = user.role

    users = await User.filter(**query_args).limit(limit).offset((page - 1) * 10)

    return [user.to_json(True) for user in users]


@router.patch("/users/{user_id}", response_model=AdminUserData)
async def edit_user(user_id: int, data: AdminUserEditData, admin: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user := await User.get_or_none(id=user_id)) is None:
        raise Errors.UNKNOWN_USER

    if data.role is not None and (not UserRole.has_value(data.role) or data.role >= admin.role) or \
            user.role >= admin.role:
        raise Errors.INVALID_ROLE

    args = data.model_dump(exclude={"mfa_enabled"}, exclude_defaults=True)
    if data.mfa_enabled is False:
        args["mfa_key"] = None

    await upload_image_or_not("avatar", args, "avatar", 640, 640)
    await user.update(**args)

    return user.to_json(True)


@router.post("/users/{user_id}/ban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user_to_ban := await User.get_or_none(id=user_id)) is None:
        raise Errors.UNKNOWN_USER
    if user_to_ban.role >= user.role:
        raise Errors.CANNOT_BAN

    await user_to_ban.update(banned=True)


@router.post("/users/{user_id}/unban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user_to_unban := await User.get_or_none(id=user_id)) is None:
        raise Errors.UNKNOWN_USER
    if user_to_unban.role >= user.role:
        raise Errors.CANNOT_UNBAN

    await user_to_unban.update(banned=False)


@router.get("/events", response_model=list[EventData])
async def get_events(user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    return [event.to_json() for event in await Event.filter(manager=user).select_related("location")]


# noinspection PyUnusedLocal
@router.post("/events", response_model=EventData)
async def add_event(data: AddEventData, user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    if (location := await Location.get_or_none(id=data.location_id)) is None:
        raise Errors.UNKNOWN_LOCATION

    create_args = data.model_dump(exclude={"location_id", "plans", "start_time", "end_time", "image"})
    create_args["location"] = location
    create_args["start_time"] = datetime.fromtimestamp(data.start_time, UTC)
    create_args["end_time"] = datetime.fromtimestamp(data.end_time, UTC)
    if data.image and S3 is not None:
        img: Image = Image.thumbnail_buffer(open_image_b64(data.image), 720, height=1280, size="force")
        image: bytes = img.write_to_buffer(".jpg[Q=85]")
        image_id = str(uuid4())
        await S3.upload_object("ticketer", f"events/{image_id}.jpg", BytesIO(image))

        create_args["image_id"] = image_id

    event = await Event.create(manager=user, **create_args)
    for plan in data.plans:
        await EventPlan.create(**plan.model_dump(), event=event)

    return event.to_json()


# noinspection PyUnusedLocal
@router.patch("/events/{event_id}", response_model=EventData)
async def edit_event(event_id: int, data: EditEventData, user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    if (event := await Event.get_or_none(id=event_id, manager=user)) is None:
        raise Errors.UNKNOWN_EVENT

    location = None
    if data.location_id is not None and (location := await Location.get_or_none(id=data.location_id)) is None:
        raise Errors.UNKNOWN_LOCATION

    args = data.model_dump(exclude={"location_id", "plans", "start_time", "end_time"}, exclude_defaults=True)
    if data.start_time is not None:
        args["start_time"] = datetime.fromtimestamp(data.start_time, UTC)
    if data.end_time is not None:
        args["end_time"] = datetime.fromtimestamp(data.end_time, UTC)
    if location is not None:
        args["location"] = location

    await upload_image_or_not("event", args)

    await event.update(**args)
    if data.plans is not None:
        await EventPlan.filter(event=event).delete()
        for plan in data.plans:
            await EventPlan.create(**plan.model_dump(), event=event)

    return event.to_json()


@router.post("/tickets/validate", response_model=AdminTicketValidationData)
async def validate_ticket(data: TicketValidationData, user: User = Depends(jwt_auth_role(UserRole.MANAGER))):
    if (ticket := JWT.decode(data.ticket, config.JWT_KEY)) is None:
        raise Errors.INVALID_TICKET
    if data.event_id != ticket["event_id"]:
        raise Errors.TICKET_ANOTHER_EVENT
    if not Event.filter(id=data.event_id, manager=user).exists():
        raise Errors.UNKNOWN_EVENT

    user = await User.get(id=ticket["user_id"])
    plan = await EventPlan.get(id=ticket["plan_id"])

    return {
        "user": {
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        "ticket_num": ticket["ticket_num"],
        "plan": plan.to_json(),
    }
