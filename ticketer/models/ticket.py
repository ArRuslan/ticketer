from __future__ import annotations

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class Ticket(Model):
    id: int = fields.BigIntField(pk=True)
    amount: int = fields.SmallIntField()
    event_plan: models.EventPlan = fields.ForeignKeyField("models.EventPlan")
    user: models.User = fields.ForeignKeyField("models.User")
