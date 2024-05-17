from httpx import AsyncClient

from ticketer import config


class Turnstile:
    URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    @classmethod
    async def verify(cls, key: str) -> bool:
        async with AsyncClient() as client:
            resp = await client.post(cls.URL, json={"secret": config.TURNSTILE_SECRET, "response": key})
            return resp.json()["success"]
