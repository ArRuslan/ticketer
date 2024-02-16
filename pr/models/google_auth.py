from tortoise import fields

from pr import models
from pr.models._utils import Model


class GoogleAuth(Model):
    id: int = fields.BigIntField(pk=True)
    email: str = fields.CharField(max_length=255, unique=True)
    user: models.User = fields.ForeignKeyField("models.User", unique=True)
    access_token: str = fields.TextField()
    refresh_token: str = fields.TextField()
    expires_at: int = fields.BigIntField()
