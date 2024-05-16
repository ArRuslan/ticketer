from __future__ import annotations

from datetime import datetime

from tortoise import fields

from pr import models
from pr.models._utils import Model


class Event(Model):
    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=255)
    description: str = fields.TextField()
    start_time: datetime = fields.DatetimeField(default=datetime.utcnow)
    end_time: datetime | None = fields.DatetimeField(null=True, default=None)
    location: models.Location = fields.ForeignKeyField("models.Location")
