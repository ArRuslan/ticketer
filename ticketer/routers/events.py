from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter

from ticketer.models import Event
from ticketer.schemas import EventSearchData

router = APIRouter(prefix="/events")


# TODO: add searching and sorting by price
@router.post("/events/search")
async def search_events(data: EventSearchData, sort_by: Literal["name", "category", "start_time"] | None = None,
                        sort_direction: Literal["asc", "desc"] = "asc", results_per_page: int = 10, page: int = 1,
                        with_plans: bool = False):
    page = max(page, 1)
    results_per_page = min(results_per_page, 50)
    results_per_page = max(results_per_page, 5)

    query_args = data.model_dump(exclude_defaults=True, exclude={"time_min", "time_max"})
    if data.time_max:
        query_args["start_time__lte"] = datetime.fromtimestamp(data.time_max, UTC)
    if data.time_min:
        query_args["start_time__gte"] = datetime.fromtimestamp(data.time_min, UTC)
    if data.name:
        del query_args["name"]
        query_args["name__contains"] = data.name

    events_query = Event.filter(**query_args).limit(results_per_page).offset((page - 1) * 10).select_related("location")
    if sort_by is not None:
        if sort_direction == "desc":
            sort_by = f"-{sort_by}"
        events_query = events_query.order_by(sort_by)

    result = []
    for event in await events_query:
        result.append(event.to_json())
        if with_plans:
            plans = await event.plans.all()
            result[-1]["plans"] = [{
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "max_tickets": plan.max_tickets,
            } for plan in plans]

    return result


@router.get("/events/{event_id}")
async def get_events(event_id: int, with_plans: bool = False):
    event = await Event.get_or_none(id=event_id).select_related("location")

    result = event.to_json()
    if with_plans:
        result["plans"] = [{
            "id": plan.id,
            "name": plan.name,
            "price": plan.price,
            "max_tickets": plan.max_tickets,
        } for plan in await event.plans.all()]

    return result
