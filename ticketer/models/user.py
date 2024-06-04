from enum import IntEnum

from tortoise import fields

from ticketer.models._utils import Model


class UserRole(IntEnum):
    USER = 0
    MANAGER = 1
    ADMIN = 999

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class User(Model):
    id: int = fields.BigIntField(pk=True)
    email: str | None = fields.CharField(max_length=255, unique=True, null=True, default=None)
    password: str | None = fields.CharField(max_length=64, null=True, default=None)
    first_name: str = fields.CharField(max_length=128)
    last_name: str = fields.CharField(max_length=128)
    avatar_id: str | None = fields.CharField(max_length=255, null=True, default=None)  # ??
    phone_number: int | None = fields.BigIntField(unique=True, null=True, default=None)
    mfa_key: str | None = fields.CharField(max_length=64, null=True, default=None)
    banned: bool = fields.BooleanField(default=False)
    role: int = fields.IntEnumField(UserRole, default=UserRole.USER)

    def to_json(self, full: bool = False) -> dict:
        if full:
            return {
                "id": self.id,
                "email": self.email,
                "has_password": self.password is not None,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "avatar_id": self.avatar_id,
                "phone_number": self.phone_number,
                "mfa_enabled": self.mfa_key is not None,
                "banned": self.banned,
                "role": self.role,
            }

        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone_number": self.phone_number,
            "avatar_id": self.avatar_id,
            "mfa_enabled": self.mfa_key is not None,
        }
