from pydantic import BaseModel

from ticketer.models import UserRole


class SuccessAuthData(BaseModel):
    token: str
    expires_at: int


class GoogleAuthUrlData(BaseModel):
    url: str


class ConnectGoogleData(SuccessAuthData):
    token: str | None
    connect: bool


class UserData(BaseModel):
    id: int
    email: str | None
    first_name: str
    last_name: str
    avatar_id: str | None
    phone_number: int | None
    mfa_enabled: bool


class AdminUserData(UserData):
    has_password: bool
    banned: bool
    role: UserRole


class EventLocationData(BaseModel):
    name: str
    longitude: float
    latitude: float


class EventData(BaseModel):
    id: int
    name: str
    description: str
    category: str
    city: str
    start_time: int
    end_time: int | None
    image_id: str | None
    location: EventLocationData | None = None


class EventPlanData(BaseModel):
    name: str
    price: float


class EventWithPlansData(EventData):
    plans: list[EventPlanData]


class AdminTicketValidationUserData(BaseModel):
    first_name: str
    last_name: str


class AdminTicketValidationData(BaseModel):
    user: AdminTicketValidationUserData
    ticket_num: int
    plan: EventPlanData


class TicketData(BaseModel):
    id: int
    amount: int
    plan: EventPlanData
    event: EventData
    can_be_cancelled: bool


class BuyTicketRespData(BaseModel):
    ticket_id: int
    total_price: float
    expires_at: int


class BuyTicketVerifiedData(BaseModel):
    ticket_id: int
    payment_state: int
    paypal_id: str | None
    expires_at: int


class PaymentMethodData(BaseModel):
    type: str
    card_number: str
    expiration_date: str
    expired: bool


class PendingConfirmationData(BaseModel):
    ticket_id: int
    expires_at: int
