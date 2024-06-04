from httpx import AsyncClient

from ticketer import config


class ReCaptcha:
    URL = "https://www.google.com/recaptcha/api/siteverify"

    @classmethod
    async def verify(cls, key: str) -> bool:
        async with AsyncClient() as client:
            resp = await client.post(cls.URL, data={"secret": config.RECAPTCHA_SECRET, "response": key})
            return resp.json()["success"]
