from base64 import b64decode
from datetime import datetime
from io import BytesIO

from magic import from_buffer

from ticketer.utils.jwt import _b64decode


def is_valid_card(card_number: str, expiration_date: str) -> bool:
    expiration_date = expiration_date.split("/")
    if len(expiration_date) != 2:
        return False
    expiration_month, expiration_year = expiration_date
    if not expiration_year.isdigit() or not expiration_month.isdigit():
        return False
    if datetime.now() > datetime(2000+int(expiration_year), int(expiration_month), 1):
        return False

    if len(card_number) != 16 or not card_number.isdigit():
        return False
    card = [int(digit) for digit in card_number]
    for idx, digit in enumerate(card):
        if idx % 2 != 0:
            continue
        digit *= 2
        if digit >= 10:
            digit = 1 + digit % 10

        card[idx] = digit

    return sum(card) % 10 == 0


def open_image_b64(image: str) -> bytes | None:
    if isinstance(image, str) and (
            image.startswith("data:image/") or image.startswith("data:application/octet-stream")) and "base64" in \
            image.split(",")[0]:
        image = b64decode(image.split(",")[1].encode("utf8"))
    else:
        return
    mime = from_buffer(image[:1024], mime=True)
    if not mime.startswith("image/") or mime[6:] not in {"png", "jpeg", "jpg", "webp"}:
        return  # Not a valid image

    return image
