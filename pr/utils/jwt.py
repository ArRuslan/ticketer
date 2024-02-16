import hmac
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha512
from json import loads, dumps
from time import time


def _b64encode(data: str | bytes | dict) -> str:
    if isinstance(data, dict):
        data = dumps(data, separators=(',', ':')).encode("utf8")
    elif isinstance(data, str):
        data = data.encode("utf8")

    return urlsafe_b64encode(data).decode("utf8").strip("=")


def _b64decode(data: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode("utf8")

    if len(data) % 4 != 0:
        data += b"=" * (-len(data) % 4)

    return urlsafe_b64decode(data)


class JWT:
    """
    Json Web Token Hmac-sha512 implementation
    """

    @staticmethod
    def decode(token: str, secret: str | bytes) -> dict | None:
        try:
            header, payload, signature = token.split(".")
            header_dict = loads(_b64decode(header).decode("utf8"))
            assert header_dict.get("alg") == "HS512"
            assert header_dict.get("typ") == "JWT"
            assert (exp := header_dict.get("exp", 0)) > time() or exp == 0
            signature = _b64decode(signature)
        except (IndexError, AssertionError, ValueError):
            return

        sig = f"{header}.{payload}".encode("utf8")
        sig = hmac.new(secret, sig, sha512).digest()
        if sig == signature:
            payload = _b64decode(payload).decode("utf8")
            return loads(payload)

    @staticmethod
    def encode(payload: dict, secret: str | bytes, expire_timestamp: int | float = 0) -> str:
        header = {
            "alg": "HS512",
            "typ": "JWT",
            "exp": int(expire_timestamp)
        }
        header = _b64encode(header)
        payload = _b64encode(payload)

        signature = f"{header}.{payload}".encode("utf8")
        signature = hmac.new(secret, signature, sha512).digest()
        signature = _b64encode(signature)

        return f"{header}.{payload}.{signature}"
