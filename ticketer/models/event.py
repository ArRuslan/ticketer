from __future__ import annotations

from datetime import datetime

from tortoise import fields

from ticketer import models
from ticketer.models._utils import Model


class Event(Model):
    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=255)
    description: str = fields.TextField()
    category: str = fields.CharField(max_length=64)
    start_time: datetime = fields.DatetimeField(default=datetime.now)
    end_time: datetime | None = fields.DatetimeField(null=True, default=None)
    location: models.Location = fields.ForeignKeyField("models.Location")
    image_id: str | None = fields.CharField(max_length=64, null=True, default=None)

    plans: fields.ReverseRelation[models.EventPlan]

    def to_json(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "start_time": int(self.start_time.timestamp()),
            "end_time": int(self.end_time.timestamp()) if self.end_time is not None else None,
            "image_id": self.image_id,
        }
        if isinstance(self.location, models.Location):
            result["location"] = {
                "name": self.location.name,
                "longitude": self.location.longitude,
                "latitude": self.location.latitude,
            }

        return result
