from httpx import AsyncClient

from pr.config import TURNSTILE_SECRET


class Turnstile:
    URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    @classmethod
    async def verify(cls, key: str) -> bool:
        async with AsyncClient() as client:
            resp = await client.post(cls.URL, content=f"secret={TURNSTILE_SECRET}&response={key}")
            return resp.json()["success"]
