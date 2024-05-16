from __future__ import annotations

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class EventPlan(Model):
    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=255)
    price: float = fields.FloatField()
    max_tickets: int = fields.SmallIntField()
    event: models.Event = fields.ForeignKeyField("models.Event")
