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

    def expired(self) -> bool:
        return self.expires_at.replace(tzinfo=UTC) < datetime.now(UTC)

    async def to_json(self, full: bool = False) -> dict:
        if full:
            if not isinstance(self.ticket, models.Ticket):
                await self.fetch_related("ticket")
            return {
                "ticket_id": self.ticket.id,
                "state": self.state,
                "paypal_id": self.paypal_id,
                "expires_at": int(self.expires_at.timestamp()),
            }

        return {
            "state": self.state,
            "expires_at": int(self.expires_at.timestamp()),
        }
