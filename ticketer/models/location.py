from tortoise import fields

from ticketer.models._utils import Model


class Location(Model):
    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=255)
    longitude: float = fields.FloatField()
    latitude: float = fields.FloatField()
