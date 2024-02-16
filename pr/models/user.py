from tortoise import fields

from pr.models._utils import Model


class User(Model):
    id: int = fields.BigIntField(pk=True)
    email: str = fields.CharField(max_length=255, unique=True)
    password: str = fields.CharField(max_length=64, null=True, default=None)
    first_name: str = fields.CharField(max_length=128)
    last_name: str = fields.CharField(max_length=128)
    avatar_id: str = fields.CharField(max_length=255, null=True, default=None)
