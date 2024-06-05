from __future__ import annotations

from datetime import datetime, timedelta, UTC

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class Ticket(Model):
    id: int = fields.BigIntField(pk=True)
    amount: int = fields.SmallIntField()
    event_plan: models.EventPlan = fields.ForeignKeyField("models.EventPlan")
    user: models.User = fields.ForeignKeyField("models.User")
    _payment: models.Payment | None = None

    async def get_payment(self) -> models.Payment:
        if self._payment is None:
            self._payment = await models.Payment.get(ticket=self)

        return self._payment

    async def can_be_cancelled(self) -> bool:
        payment = await self.get_payment()
        return (self.event_plan.event.start_time.replace(tzinfo=UTC) - datetime.now(UTC)) > timedelta(hours=3) or \
            payment.state != models.PaymentState.DONE
