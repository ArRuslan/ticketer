from datetime import datetime, timedelta, UTC
from enum import IntEnum

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class PaymentState(IntEnum):
    AWAITING_VERIFICATION = 0
    AWAITING_PAYMENT = 1
    DONE = 2


def gen_expires_at():
    return datetime.now(UTC) + timedelta(minutes=15)


class Payment(Model):
    id: int = fields.BigIntField(pk=True)
    ticket: models.Ticket = fields.ForeignKeyField("models.Ticket", unique=True)
    state: PaymentState = fields.IntEnumField(PaymentState, default=PaymentState.AWAITING_VERIFICATION)
    paypal_id: str | None = fields.CharField(max_length=255, null=True, default=None)
    expires_at: datetime = fields.DatetimeField(default=gen_expires_at)
