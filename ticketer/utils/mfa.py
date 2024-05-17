import re
from base64 import b32decode
from hmac import new
from struct import pack, unpack
from time import time


class MFA:
    _re = re.compile(r'^[A-Z0-9]{16}$')

    def __init__(self, key: str):
        self.key = str(key).upper()

    def getCode(self, timestamp: int | float | None = None) -> str:
        if timestamp is None:
            timestamp = time()
        key = b32decode(self.key.upper() + '=' * ((8 - len(self.key)) % 8))
        counter = pack('>Q', int(timestamp / 30))
        mac = new(key, counter, "sha1").digest()
        offset = mac[-1] & 0x0f
        binary = unpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
        return str(binary)[-6:].zfill(6)

    def getCodes(self) -> set[str]:
        return {self.getCode(time() - 5), self.getCode(time() + 1)}

    @property
    def valid(self) -> bool:
        return bool(self._re.match(self.key))
