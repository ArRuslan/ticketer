from __future__ import annotations

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class UserDevice(Model):
    id: int = fields.BigIntField(pk=True)
    device_token: str = fields.CharField(max_length=255)
    user: models.User = fields.ForeignKeyField("models.User")
