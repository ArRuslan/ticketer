from datetime import datetime, timedelta, UTC
from time import time
from typing import Annotated

from bcrypt import checkpw
from fastapi import FastAPI, HTTPException, Form, Depends, Header
from fastui import FastUI, AnyComponent, components as c, prebuilt_html
from fastui.components.display import DisplayLookup
from fastui.events import GoToEvent, PageEvent, AuthEvent
from fastui.forms import SelectOption, fastui_form
from pydantic import BaseModel, EmailStr, Field
from starlette.responses import HTMLResponse

from ticketer import config
from ticketer.errors import Errors
from ticketer.models import User, UserRole, AuthSession, Event, Location, EventPlan, UserPydantic, EventPydantic
from ticketer.utils.jwt import JWT

app = FastAPI()


class LoginForm(BaseModel):
    email: EmailStr = Field(title='Email Address', json_schema_extra={'autocomplete': 'email'})
    password: str = Field(title='Password', json_schema_extra={'autocomplete': 'current-password'})


async def auth_admin(authorization: str = Header(default="")) -> User | None:
    authorization = authorization.split(" ")[-1]
    if not authorization or (data := JWT.decode(authorization, config.JWT_KEY)) is None:
        return
    if "user" not in data or "session" not in data or "token" not in data:
        return

    sess = await AuthSession.get_or_none(
        id=data["session"], user__id=data["user"], token=data["token"], user__role__gte=UserRole.MANAGER,
    ).select_related("user")
    if sess is None:
        return

    return sess.user


def user_redirect_to(user: User) -> str:
    if user.role == UserRole.ADMIN:
        return "users"
    elif user.role == UserRole.MANAGER:
        return "events"

    return ""


def get_ban_unban(user: User) -> str:
    return "unban" if user.banned else "ban"


@app.get('/api/admin-ui/login/', response_model=FastUI, response_model_exclude_none=True)
@app.get('/api/admin-ui/login', response_model=FastUI, response_model_exclude_none=True)
def admin_login(user: User | None = Depends(auth_admin)) -> list[AnyComponent]:
    if user is not None:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/{user_redirect_to(user)}"))]

    return [
        c.Page(
            components=[
                c.Heading(text='Login', level=3),
                c.ModelForm(model=LoginForm, submit_url='/api/admin-ui/login', display_mode='page'),
            ]
        )
    ]


@app.post("/api/admin-ui/login/", response_model=FastUI, response_model_exclude_none=True)
@app.post("/api/admin-ui/login", response_model=FastUI, response_model_exclude_none=True)
async def admin_login_post(form: Annotated[LoginForm, fastui_form(LoginForm)]) -> list[AnyComponent]:
    if (user := await User.get_or_none(email=form.email, role__gte=UserRole.MANAGER)) is None:
        raise Errors.WRONG_CREDENTIALS

    if not checkpw(form.password.encode("utf8"), user.password.encode("utf8")):
        raise Errors.WRONG_CREDENTIALS

    session = await AuthSession.create(user=user)

    return [c.FireEvent(event=AuthEvent(token=session.to_jwt(), url=f"/admin-ui/{user_redirect_to(user)}"))]


@app.get("/api/admin-ui/users/", response_model=FastUI, response_model_exclude_none=True)
@app.get("/api/admin-ui/users", response_model=FastUI, response_model_exclude_none=True)
async def users_table(admin: User | None = Depends(auth_admin)) -> list[AnyComponent]:
    if admin is None or admin.role != UserRole.ADMIN:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    users = [await UserPydantic.from_tortoise_orm(user) for user in await User.filter(role__lt=admin.role).limit(25)]

    return [
        c.Page(
            components=[
                c.Heading(text='Users', level=2),
                c.Table(
                    data=users,
                    data_model=UserPydantic,
                    columns=[
                        DisplayLookup(field="email", on_click=GoToEvent(url="/admin-ui/users/{id}/")),
                        DisplayLookup(field="first_name"),
                        DisplayLookup(field="banned"),
                    ],
                ),
            ]
        ),
    ]


@app.post("/api/admin-ui/users/{user_id}/edit/", response_model=FastUI, response_model_exclude_none=True)
@app.post("/api/admin-ui/users/{user_id}/edit", response_model=FastUI, response_model_exclude_none=True)
async def edit_user(user_id: int, first_name: str = Form(), last_name: str = Form(), role: int = Form(),
                    admin: User | None = Depends(auth_admin)):
    if admin is None or admin.role != UserRole.ADMIN:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (user := await User.get_or_none(id=user_id, role__lt=admin.role)) is None:
        raise HTTPException(status_code=404, detail="User not found")

    await user.update(
        first_name=first_name,
        last_name=last_name,
        role=role,
    )

    return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/users/{user_id}?{int(time())}"))]


@app.post("/api/admin-ui/users/{user_id}/ban/")
@app.post("/api/admin-ui/users/{user_id}/ban")
async def ban_user(user_id: int, admin: User | None = Depends(auth_admin)):
    if admin is None or admin.role != UserRole.ADMIN:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (user := await User.get_or_none(id=user_id, role__lt=admin.role)) is None:
        raise HTTPException(status_code=404, detail="User not found")

    await user.update(banned=True)
    return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/users/{user_id}?{int(time())}"))]


@app.post("/api/admin-ui/users/{user_id}/unban/")
@app.post("/api/admin-ui/users/{user_id}/unban")
async def unban_user(user_id: int, admin: User | None = Depends(auth_admin)):
    if admin is None or admin.role != UserRole.ADMIN:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (user := await User.get_or_none(id=user_id, role__lt=admin.role)) is None:
        raise HTTPException(status_code=404, detail="User not found")

    await user.update(banned=False)
    return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/users/{user_id}?{int(time())}"))]


@app.get("/api/admin-ui/users/{user_id}/", response_model=FastUI, response_model_exclude_none=True)
@app.get("/api/admin-ui/users/{user_id}", response_model=FastUI, response_model_exclude_none=True)
async def user_info(user_id: int, admin: User | None = Depends(auth_admin)) -> list[AnyComponent]:
    if admin is None or admin.role != UserRole.ADMIN:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (user := await User.get_or_none(id=user_id, role__lt=admin.role)) is None:
        raise HTTPException(status_code=404, detail="User not found")

    user = await UserPydantic.from_tortoise_orm(user)
    return [
        c.Page(
            components=[
                c.Link(components=[c.Text(text='<- Back')], on_click=GoToEvent(url='/admin-ui/users')),
                c.Heading(text=user.email, level=2),
                c.Details(data=user),
                c.Div(components=[
                    c.Button(
                        text=get_ban_unban(user).title(), named_style='warning', on_click=PageEvent(name='ban-modal')
                    ),
                    c.Button(
                        text="Edit", on_click=PageEvent(name='edit-modal')
                    ),
                ]),
                c.Modal(
                    title='Edit user',
                    body=[
                        c.Form(
                            form_fields=[
                                c.FormFieldInput(
                                    name='first_name',
                                    title='First Name',
                                    initial=user.first_name,
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='last_name',
                                    title='Last Name',
                                    initial=user.last_name,
                                    required=True,
                                ),
                                c.FormFieldSelect(
                                    name='role',
                                    title='Role',
                                    initial=str(user.role),
                                    required=True,
                                    options=[
                                        SelectOption(label="User", value="0"),
                                        SelectOption(label="Manager", value="1"),
                                    ]
                                ),
                            ],
                            loading=[c.Spinner(text='Editing...')],
                            submit_url=f"/api/admin-ui/users/{user.id}/edit",
                            submit_trigger=PageEvent(name='edit-form-submit'),
                            footer=[],
                        ),
                    ],
                    footer=[
                        c.Button(
                            text='Cancel', named_style='secondary', on_click=PageEvent(name='edit-form', clear=True)
                        ),
                        c.Button(
                            text='Submit', on_click=PageEvent(name='edit-form-submit')
                        ),
                    ],
                    open_trigger=PageEvent(name='edit-modal'),
                ),
                c.Modal(
                    title=f"{get_ban_unban(user).title()} user?",
                    body=[
                        c.Paragraph(text="Are you sure you want to ban this user?"),
                        c.Form(
                            form_fields=[],
                            loading=[c.Spinner(text='...')],
                            submit_url=f"/api/admin-ui/users/{user.id}/{get_ban_unban(user)}",
                            submit_trigger=PageEvent(name='ban-form-submit'),
                            footer=[],
                        ),
                    ],
                    footer=[
                        c.Button(
                            text='Cancel', named_style='secondary', on_click=PageEvent(name='ban-form', clear=True)
                        ),
                        c.Button(
                            text=get_ban_unban(user).title(), on_click=PageEvent(name='ban-form-submit')
                        ),
                    ],
                    open_trigger=PageEvent(name='ban-modal'),
                ),
            ]
        ),
    ]


@app.post("/api/admin-ui/events/{event_id}/edit/", response_model=FastUI, response_model_exclude_none=True)
@app.post("/api/admin-ui/events/{event_id}/edit", response_model=FastUI, response_model_exclude_none=True)
async def edit_event(event_id: int, name: str = Form(), description: str = Form(), category: str = Form(),
                     city: str = Form(), admin: User | None = Depends(auth_admin)):
    if admin is None:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (event := await Event.get_or_none(id=event_id, manager=admin)) is None:
        raise HTTPException(status_code=404, detail="Event not found")

    await event.update(
        name=name,
        description=description,
        category=category,
        city=city,
    )

    return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/events/{event_id}?{int(time())}"))]


@app.post("/api/admin-ui/events/", response_model=FastUI, response_model_exclude_none=True)
@app.post("/api/admin-ui/events", response_model=FastUI, response_model_exclude_none=True)
async def add_event(name: str = Form(), description: str = Form(), category: str = Form(),
                    city: str = Form(), admin: User | None = Depends(auth_admin)):
    if admin is None:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    location = await Location.create(name="Test location", longitude=0, latitude=0)
    event = await Event.create(
        name=name,
        description=description,
        category=category,
        city=city,
        start_time=datetime.now(UTC) + timedelta(days=7),
        location=location,
        manager=admin,
    )
    await EventPlan.create(name="Basic", price=100, max_tickets=100, event=event)

    return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/events/{event.id}?{int(time())}"))]


@app.get("/api/admin-ui/events/", response_model=FastUI, response_model_exclude_none=True)
@app.get("/api/admin-ui/events", response_model=FastUI, response_model_exclude_none=True)
async def events_table(admin: User | None = Depends(auth_admin)) -> list[AnyComponent]:
    if admin is None:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    events = [await EventPydantic.from_tortoise_orm(event) for event in await Event.filter(manager=admin)]

    return [
        c.Page(
            components=[
                c.Heading(text='Events', level=2),
                c.Button(text="Add", on_click=PageEvent(name='add-modal')),
                c.Table(
                    data=events,
                    data_model=EventPydantic,
                    columns=[
                        DisplayLookup(field="name", on_click=GoToEvent(url="/admin-ui/events/{id}")),
                        DisplayLookup(field="category"),
                        DisplayLookup(field="city"),
                        DisplayLookup(field="start_time"),
                    ],
                ),

                c.Modal(
                    title='Add event',
                    body=[
                        c.Form(
                            form_fields=[
                                c.FormFieldInput(
                                    name='name',
                                    title='Name',
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='description',
                                    title='Description',
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='category',
                                    title='Category',
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='city',
                                    title='City',
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='max_tickets',
                                    title='Maximum number of tickets',
                                    required=True,
                                    html_type="number",
                                ),
                            ],
                            loading=[c.Spinner(text='Adding...')],
                            submit_url=f"/api/admin-ui/events",
                            submit_trigger=PageEvent(name='add-form-submit'),
                            footer=[],
                        ),
                    ],
                    footer=[
                        c.Button(
                            text='Cancel', named_style='secondary', on_click=PageEvent(name='add-form', clear=True)
                        ),
                        c.Button(
                            text='Submit', on_click=PageEvent(name='add-form-submit')
                        ),
                    ],
                    open_trigger=PageEvent(name='add-modal'),
                ),
            ]
        ),
    ]


@app.get("/api/admin-ui/events/{event_id}/", response_model=FastUI, response_model_exclude_none=True)
@app.get("/api/admin-ui/events/{event_id}", response_model=FastUI, response_model_exclude_none=True)
async def event_info(event_id: int, admin: User | None = Depends(auth_admin)) -> list[AnyComponent]:
    if admin is None:
        return [c.FireEvent(event=GoToEvent(url=f"/admin-ui/login"))]

    if (event := await Event.get_or_none(id=event_id, manager=admin)) is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = await EventPydantic.from_tortoise_orm(event)
    return [
        c.Page(
            components=[
                c.Link(components=[c.Text(text='<- Back')], on_click=GoToEvent(url='/admin-ui/events')),
                c.Heading(text=event.name, level=2),
                c.Details(data=event),
                c.Div(components=[
                    c.Button(
                        text="Edit", on_click=PageEvent(name='edit-modal')
                    ),
                ]),
                c.Modal(
                    title='Edit event',
                    body=[
                        c.Form(
                            form_fields=[
                                c.FormFieldInput(
                                    name='name',
                                    title='Name',
                                    initial=event.name,
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='description',
                                    title='Description',
                                    initial=event.description,
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='category',
                                    title='Category',
                                    initial=event.category,
                                    required=True,
                                ),
                                c.FormFieldInput(
                                    name='city',
                                    title='City',
                                    initial=event.city,
                                    required=True,
                                ),
                                # c.FormFieldInput(
                                #    name='max_tickets',
                                #    title='Maximum number of tickets',
                                #    initial=event.max_tickets,
                                #    required=True,
                                #    html_type="number",
                                # ),
                            ],
                            loading=[c.Spinner(text='Editing...')],
                            submit_url=f"/api/admin-ui/events/{event.id}/edit",
                            submit_trigger=PageEvent(name='edit-form-submit'),
                            footer=[],
                        ),
                    ],
                    footer=[
                        c.Button(
                            text='Cancel', named_style='secondary', on_click=PageEvent(name='edit-form', clear=True)
                        ),
                        c.Button(
                            text='Submit', on_click=PageEvent(name='edit-form-submit')
                        ),
                    ],
                    open_trigger=PageEvent(name='edit-modal'),
                ),
            ]
        ),
    ]


@app.get('/admin-ui/{path:path}')
async def html_landing() -> HTMLResponse:
    return HTMLResponse(prebuilt_html(title='Ticketer admin panel'))
