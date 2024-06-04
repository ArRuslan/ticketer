from pathlib import Path

from aerich import Command
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from ticketer import config
from ticketer.exceptions import CustomBodyException
from ticketer.routers import admin, auth, users_me, events, tickets

app = FastAPI()
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(users_me.router)
app.include_router(events.router)
app.include_router(tickets.router)


@app.on_event("startup")
async def migrate_orm():  # pragma: no cover
    if config.DB_CONNECTION_STRING == "sqlite://:memory:":
        return
    migrations_dir = "data/migrations"

    command = Command({
        "connections": {"default": config.DB_CONNECTION_STRING},
        "apps": {"models": {"models": ["ticketer.models", "aerich.models"], "default_connection": "default"}},
    }, location=migrations_dir)
    await command.init()
    if Path(migrations_dir).exists():
        await command.migrate()
        await command.upgrade(True)
    else:
        await command.init_db(True)
    await Tortoise.close_connections()


register_tortoise(
    app,
    db_url=config.DB_CONNECTION_STRING,
    modules={"models": ["ticketer.models"]},
    generate_schemas=True,
)


# noinspection PyUnusedLocal
@app.exception_handler(CustomBodyException)
async def custom_exception_handler(request: Request, exc: CustomBodyException):
    return JSONResponse(status_code=exc.status_code, content=exc.body)
