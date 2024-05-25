from bcrypt import gensalt, hashpw, checkpw
from fastapi import APIRouter
from fastapi import Depends

from ticketer.exceptions import BadRequestException
from ticketer.models import User, PaymentMethod
from ticketer.schemas import EditProfileData, AddPaymentMethodData
from ticketer.utils import is_valid_card
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.mfa import MFA

router = APIRouter(prefix="/users/me")


@router.get("")
async def get_user_info(user: User = Depends(jwt_auth)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "mfa_enabled": user.mfa_key is not None,
    }


@router.patch("")
async def edit_user_info(data: EditProfileData, user: User = Depends(jwt_auth)):
    require_password = data.mfa_key is not None or data.new_password is not None or data.email is not None \
                       or data.phone_number is not None
    if data.mfa_key and user.mfa_key is not None:
        raise BadRequestException("Two-factory authentication is already enabled.")
    elif data.mfa_key is None and user.mfa_key is None:
        raise BadRequestException("Two-factory authentication is already disabled.")

    if require_password and not data.password:
        raise BadRequestException("You need to enter your password.")
    elif require_password and data.password:
        if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
            raise BadRequestException("Wrong password.")

    if data.mfa_key:
        mfa = MFA(data.mfa_key)
        if not mfa.valid:
            raise BadRequestException("Invalid two-factor authentication key.")
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")
    elif data.mfa_key is None and user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise BadRequestException("Invalid two-factor authentication code.")

    # TODO: check if phone number is already used
    j_data = data.model_dump(exclude_defaults=True, exclude={"password", "new_password"})
    if data.new_password is not None:
        j_data["password"] = hashpw(data.new_password.encode("utf8"), gensalt()).decode()

    if j_data:
        await user.update(**j_data)

    return await get_user_info(user)


@router.get("/payment")
async def get_payment_methods(user: User = Depends(jwt_auth)):
    payment_methods = await PaymentMethod.filter(user=user)

    return [{
        "type": method.type,
        "card_number": method.card_number,
        "expiration_date": method.expiration_date,
        "expired": method.expired(),
    } for method in payment_methods]


@router.post("/payment")
async def add_payment_method(data: AddPaymentMethodData, user: User = Depends(jwt_auth)):
    if not is_valid_card(data.card_number, data.expiration_date):
        raise BadRequestException("Card details you provided are invalid.")

    await PaymentMethod.get_or_create(user=user, type=data.type, card_number=data.card_number, defaults={
        "expiration_date": data.expiration_date,
    })

    return {
        "type": data.type,
        "card_number": data.card_number,
        "expiration_date": data.expiration_date,
        "expired": False,
    }


@router.delete("/payment/{card_number}", status_code=204)
async def delete_payment_method(card_number: str, user: User = Depends(jwt_auth)):
    await PaymentMethod.filter(user=user, card_number=card_number).delete()
