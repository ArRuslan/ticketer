from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class BaseAuthData(BaseModel):
    email: EmailStr
    password: str
    captcha_key: str | None = None


class LoginData(BaseAuthData):
    mfa_code: str | None = None


class RegisterData(BaseAuthData):
    first_name: str
    last_name: str


class GoogleOAuthData(BaseModel):
    code: str
    state: str | None = None


class EditProfileData(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None
    mfa_key: str | None = ""
    mfa_code: str | None = None
    new_password: str | None = None
    phone_number: int | None = None


class AddPaymentMethodData(BaseModel):
    type: str
    card_number: str
    expiration_date: str


class BuyTicketData(BaseModel):
    event_id: int
    plan_id: int
    card_number: str
    amount: int = 1
    mfa_code: str | None = None


class EventSearchData(BaseModel):
    name: str | None = None
    category: str | None = None
    time_min: int | None = None
    time_max: int | None = None
    city: str | None = None
    #price_min: int | None = None
    #price_max: int | None = None


class AdminUserSearchData(BaseModel):
    email: str | None = None
    phone_number: int | None = None


class EventPlanData(BaseModel):
    name: str
    price: float
    max_tickets: int


class AddEventData(BaseModel):
    name: str
    description: str
    category: str
    start_time: int
    end_time: int
    location_id: int
    image: str | None = None  # TODO: validate image
    plans: list[EventPlanData] = Field(min_length=1)


class EditEventData(AddEventData):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    start_time: int | None = None
    end_time: int | None = None
    location_id: int | None = None
    image: str | None = None  # TODO: validate image
    plans: list[EventPlanData] | None = Field(min_length=1, default=None)
