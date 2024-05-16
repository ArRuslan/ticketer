from time import time

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class ExternalAuth(Model):
    id: int = fields.BigIntField(pk=True)
    service: str = fields.CharField(max_length=64)
    service_id: str = fields.CharField(max_length=255, unique=True)
    user: models.User = fields.ForeignKeyField("models.User", unique=True)
    access_token: str = fields.TextField()
    refresh_token: str | None = fields.TextField(null=True)
    expires_at: int | None = fields.BigIntField(null=True)

    def expired(self) -> bool:
        return (time() > self.expires_at) if self.expires_at is not None else False
