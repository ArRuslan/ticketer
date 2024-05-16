from datetime import datetime

from tortoise import fields

from pr import models
from pr.models._utils import Model


class PaymentMethod(Model):
    id: int = fields.BigIntField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    type: str = fields.CharField(max_length=64)
    card_number: str = fields.CharField(max_length=20)
    expiration_date: str = fields.CharField(max_length=5)

    def expired(self) -> bool:
        expiration_date = datetime.strptime(self.expiration_date, "%d/%y")
        return expiration_date > datetime.now()
