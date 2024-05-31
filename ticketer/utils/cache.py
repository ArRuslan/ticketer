import json

from redis.asyncio import Redis

from ticketer import config


class RedisCache:
    _connection: Redis | None = None

    @classmethod
    async def _get_client(cls) -> Redis:
        if cls._connection is None:
            cls._connection = Redis.from_url(config.REDIS_URL)
            await cls._connection.ping()

        return cls._connection

    @staticmethod
    def _hash(tag: str, *args) -> str:
        key = tag

        for arg in args:
            if isinstance(arg, bool):
                arg = int(arg)
            elif not isinstance(arg, str):
                arg = str(arg)

            arg = hash(arg)
            key = f"{key}:{hex(arg)[2:]}"

        return key

    @classmethod
    async def get(cls, tag: str, *args) -> dict | list | None:
        client = await cls._get_client()
        key = cls._hash(tag, *args)
        value = await client.get(key)

        return json.loads(value) if value is not None else None

    @classmethod
    async def put(cls, tag: str, obj: dict | list, *args, expires_in: int | None = None) -> None:
        client = await cls._get_client()
        key = cls._hash(tag, *args)

        await client.set(key, json.dumps(obj), ex=expires_in)

    @classmethod
    async def delete(cls, tag: str, *args) -> None:
        client = await cls._get_client()
        key = cls._hash(tag, *args)

        await client.delete(key)
