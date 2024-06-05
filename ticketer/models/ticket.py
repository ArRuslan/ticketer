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

    async def can_be_cancelled(self) -> bool:
        payment = await models.Payment.get(ticket=self)
        return (self.event_plan.event.start_time.replace(tzinfo=UTC) - datetime.now(UTC)) > timedelta(hours=3) or \
            payment.state != models.PaymentState.DONE
