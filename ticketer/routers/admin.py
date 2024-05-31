from datetime import datetime, UTC
from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends
from pyvips import Image

from ticketer import config
from ticketer.config import S3
from ticketer.exceptions import NotFoundException, ForbiddenException, BadRequestException
from ticketer.models import User, UserRole, Location, Event, EventPlan
from ticketer.response_schemas import AdminUserData, EventData, AdminTicketValidationData
from ticketer.schemas import AdminUserSearchData, AddEventData, EditEventData, TicketValidationData
from ticketer.utils import open_image_b64
from ticketer.utils.jwt import JWT
from ticketer.utils.jwt_auth import jwt_auth_role

router = APIRouter(prefix="/admin")


@router.post("/users", response_model=list[AdminUserData])
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


@router.post("/users/{user_id}/ban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user_to_ban := await User.get_or_none(id=user_id)) is None:
        raise NotFoundException("Unknown user.")
    if user_to_ban.role >= user.role:
        raise ForbiddenException("You cannot ban this user.")

    await user_to_ban.update(banned=True)


@router.post("/users/{user_id}/unban", status_code=204)
async def ban_user(user_id: int, user: User = Depends(jwt_auth_role(UserRole.ADMIN))):
    if (user_to_unban := await User.get_or_none(id=user_id)) is None:
        raise NotFoundException("Unknown user.")
    if user_to_unban.role >= user.role:
        raise ForbiddenException("You cannot unban this user.")

    await user_to_unban.update(banned=False)


# noinspection PyUnusedLocal
@router.post("/events", dependencies=[Depends(jwt_auth_role(UserRole.MANAGER))], response_model=EventData)
async def add_event(data: AddEventData):
    if (location := await Location.get_or_none(id=data.location_id)) is None:
        raise NotFoundException("Unknown location.")

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

    event = await Event.create(**create_args)
    for plan in data.plans:
        await EventPlan.create(**plan.model_dump(), event=event)

    return event.to_json()


# noinspection PyUnusedLocal
@router.patch("/events/{event_id}", dependencies=[Depends(jwt_auth_role(UserRole.MANAGER))], response_model=EventData)
async def edit_event(event_id: int, data: EditEventData):
    if (event := await Event.get_or_none(id=event_id)) is None:
        raise NotFoundException("Unknown event.")

    location = None
    if data.location_id is not None and (location := await Location.get_or_none(id=data.location_id)) is None:
        raise NotFoundException("Unknown location.")

    args = data.model_dump(exclude={"location_id", "plans", "start_time", "end_time"}, exclude_defaults=True)
    if data.start_time is not None:
        args["start_time"] = datetime.fromtimestamp(data.start_time, UTC)
    if data.end_time is not None:
        args["end_time"] = datetime.fromtimestamp(data.end_time, UTC)
    if location is not None:
        args["location"] = location
    if "image" in args and S3 is not None:
        if args["image"] is not None:
            img: Image = Image.thumbnail_buffer(open_image_b64(args["image"]), 720, height=1280, size="force")
            image: bytes = img.write_to_buffer(".jpg[Q=85]")
            image_id = str(uuid4())
            await S3.upload_object("ticketer", f"events/{image_id}.jpg", BytesIO(image))
        else:
            image_id = None

        args["image_id"] = image_id
        del args["image"]

    await event.update(**args)
    if data.plans is not None:
        await EventPlan.filter(event=event).delete()
        for plan in data.plans:
            await EventPlan.create(**plan.model_dump(), event=event)

    return event.to_json()


@router.post("/tickets/validate", dependencies=[Depends(jwt_auth_role(UserRole.MANAGER))],
             response_model=AdminTicketValidationData)
async def validate_ticket(data: TicketValidationData):
    if (ticket := JWT.decode(data.ticket, config.JWT_KEY)) is None:
        raise BadRequestException("Invalid ticket.")
    if data.event_id != ticket["event_id"]:
        raise BadRequestException("Ticket is issued for another event.")

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
