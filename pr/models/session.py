from base64 import b64encode
from datetime import datetime, timedelta
from os import urandom

from tortoise import fields

from pr import models
from pr.config import JWT_KEY
from pr.models._utils import Model
from pr.utils.jwt import JWT


def gen_token():
    return b64encode(urandom(32)).decode("utf8")


def gen_expires_at():
    return datetime.utcnow() + timedelta(days=7)


class AuthSession(Model):
    id: int = fields.BigIntField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    token: str = fields.CharField(max_length=64, default=gen_token)
    expires: datetime = fields.DatetimeField(default=gen_expires_at)

    def to_jwt(self) -> str:
        return JWT.encode(
            payload={"user": self.user.id, "session": self.id, "token": self.token},
            secret=JWT_KEY,
            expire_timestamp=self.expires.timestamp(),
        )
