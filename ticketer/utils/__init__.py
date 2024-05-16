from datetime import datetime


def is_valid_card(card_number: str, expiration_date: str) -> bool:
    expiration_date = expiration_date.split("/")
    if len(expiration_date) != 2:
        return False
    expiration_year, expiration_month = expiration_date
    if not expiration_year.isdigit() or not expiration_month.isdigit():
        return False
    if datetime.now() > datetime(2000+expiration_year, expiration_month, 1):
        return False

    if len(card_number) != 16 or not card_number.isdigit():
        return False
    card = [int(digit) for digit in card_number]
    for idx, digit in enumerate(card):
        if idx % 2 != 0:
            continue
        digit *= 2
        if digit > 10:
            digit = 1 + digit % 10

        card[idx] = digit

    return sum(card) % 10 == 0

