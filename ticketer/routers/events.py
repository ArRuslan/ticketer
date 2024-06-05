from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter

from ticketer.errors import Errors
from ticketer.models import Event, EventPlan
from ticketer.response_schemas import EventWithPlansData, EventData
from ticketer.schemas import EventSearchData
from ticketer.utils.cache import RedisCache

router = APIRouter(prefix="/events")


@router.post("/search", response_model=list[EventWithPlansData] | list[EventData])
async def search_events(data: EventSearchData, sort_by: Literal["name", "category", "start_time"] | None = None,
                        sort_direction: Literal["asc", "desc"] = "asc", results_per_page: int = 10, page: int = 1,
                        with_plans: bool = False):
    page = max(page, 1)
    results_per_page = min(results_per_page, 50)
    results_per_page = max(results_per_page, 5)

    cache_params = (page, results_per_page, data.name, data.category, data.city, data.time_min, data.time_max, sort_by,
                    sort_direction, with_plans)
    cached = await RedisCache.get("search", *cache_params)
    if cached is not None:  # pragma: no cover
        return cached

    query_args = data.model_dump(exclude_defaults=True, exclude={"time_min", "time_max"})
    if data.time_max:
        query_args["start_time__lte"] = datetime.fromtimestamp(data.time_max, UTC)
    if data.time_min:
        query_args["start_time__gte"] = datetime.fromtimestamp(data.time_min, UTC)
    if data.name:
        del query_args["name"]
        query_args["name__contains"] = data.name

    events_query = Event.filter(**query_args).limit(results_per_page).offset((page - 1) * results_per_page)\
        .select_related("location")
    if sort_by is not None:
        if sort_direction == "desc":
            sort_by = f"-{sort_by}"
        events_query = events_query.order_by(sort_by)

    result = []
    for event in await events_query:
        result.append(event.to_json())
        if with_plans:
            plans = await EventPlan.filter(event=event)
            result[-1]["plans"] = [{
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "max_tickets": plan.max_tickets,
            } for plan in plans]

    await RedisCache.put("search", result, *cache_params, expires_in=60)
    return result


@router.get("/{event_id}", response_model=EventWithPlansData | EventData)
async def get_events(event_id: int, with_plans: bool = False):
    if (event := await Event.get_or_none(id=event_id).select_related("location")) is None:
        raise Errors.UNKNOWN_EVENT

    result = event.to_json()
    if with_plans:
        result["plans"] = [{
            "id": plan.id,
            "name": plan.name,
            "price": plan.price,
            "max_tickets": plan.max_tickets,
        } for plan in await EventPlan.filter(event=event)]

    return result
