from tortoise.contrib.pydantic import pydantic_model_creator

from .user import User, UserRole
from .session import AuthSession
from .external_auth import ExternalAuth
from .location import Location
from .event import Event
from .payment_method import PaymentMethod
from .event_plan import EventPlan
from .ticket import Ticket
from .payment import Payment, PaymentState
from .user_device import UserDevice


UserPydantic = pydantic_model_creator(User, exclude=("mfa_key", "password"))
EventPydantic = pydantic_model_creator(Event)
