from tortoise import fields

from ticketer.models._utils import Model


class User(Model):
    id: int = fields.BigIntField(pk=True)
    email: str | None = fields.CharField(max_length=255, unique=True, null=True, default=None)
    password: str | None = fields.CharField(max_length=64, null=True, default=None)
    first_name: str = fields.CharField(max_length=128)
    last_name: str = fields.CharField(max_length=128)
    avatar_id: str | None = fields.CharField(max_length=255, null=True, default=None)  # ??
    phone_number: int | None = fields.BigIntField(unique=True, null=True, default=None)
    mfa_key: str | None = fields.CharField(max_length=64, null=True, default=None)
    # ?? role: str = fields.CharField(max_length=32, default="user")  # user/manager/admin ?
