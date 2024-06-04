from bcrypt import gensalt, hashpw, checkpw
from fastapi import APIRouter
from fastapi import Depends

from ticketer.errors import Errors
from ticketer.models import User, PaymentMethod, UserDevice
from ticketer.response_schemas import UserData, PaymentMethodData
from ticketer.schemas import EditProfileData, AddPaymentMethodData, AddPushDeviceData
from ticketer.utils import is_valid_card
from ticketer.utils.cache import RedisCache
from ticketer.utils.jwt_auth import jwt_auth
from ticketer.utils.mfa import MFA

router = APIRouter(prefix="/users/me")


@router.get("", response_model=UserData)
async def get_user_info(user: User = Depends(jwt_auth)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "avatar_id": user.avatar_id,
        "mfa_enabled": user.mfa_key is not None,
    }


@router.patch("", response_model=UserData)
async def edit_user_info(data: EditProfileData, user: User = Depends(jwt_auth)):
    require_password = data.mfa_key is not None or data.new_password is not None or data.email is not None \
                       or data.phone_number is not None
    if data.mfa_key and user.mfa_key is not None:
        raise Errors.MFA_ALREADY_ENABLED
    elif data.mfa_key is None and user.mfa_key is None:
        raise Errors.MFA_ALREADY_DISABLED

    if require_password and not data.password:
        raise Errors.NEED_PASSWORD
    elif require_password and data.password:
        if not checkpw(data.password.encode("utf8"), user.password.encode("utf8")):
            raise Errors.WRONG_PASSWORD

    if data.mfa_key:
        mfa = MFA(data.mfa_key)
        if not mfa.valid:
            raise Errors.WRONG_MFA_KEY
        if data.mfa_code not in mfa.getCodes():
            raise Errors.WRONG_MFA_CODE
    elif data.mfa_key is None and user.mfa_key is not None:
        mfa = MFA(user.mfa_key)
        if data.mfa_code not in mfa.getCodes():
            raise Errors.WRONG_MFA_CODE

    if data.phone_number is not None and await User.filter(phone_number=data.phone_number).exists():
        raise Errors.PHONE_NUMBER_USED

    j_data = data.model_dump(exclude_defaults=True, exclude={"password", "new_password"})
    if data.new_password is not None:
        j_data["password"] = hashpw(data.new_password.encode("utf8"), gensalt()).decode()

    if j_data:
        await user.update(**j_data)

    return await get_user_info(user)


@router.get("/payment", response_model=list[PaymentMethodData])
async def get_payment_methods(user: User = Depends(jwt_auth)):
    cached = await RedisCache.get("payment_methods", user.id)
    if cached is not None:
        return cached

    payment_methods = await PaymentMethod.filter(user=user)

    result = [{
        "type": method.type,
        "card_number": method.card_number,
        "expiration_date": method.expiration_date,
        "expired": method.expired(),
    } for method in payment_methods]

    await RedisCache.put("payment_methods", result, user.id, expires_in=600)
    return result


@router.post("/payment", response_model=PaymentMethodData)
async def add_payment_method(data: AddPaymentMethodData, user: User = Depends(jwt_auth)):
    if not is_valid_card(data.card_number, data.expiration_date):
        raise Errors.INVALID_CARD_DETAILS

    await PaymentMethod.get_or_create(user=user, type=data.type, card_number=data.card_number, defaults={
        "expiration_date": data.expiration_date,
    })
    await RedisCache.delete("payment_methods", user.id)

    return {
        "type": data.type,
        "card_number": data.card_number,
        "expiration_date": data.expiration_date,
        "expired": False,
    }


@router.delete("/payment/{card_number}", status_code=204)
async def delete_payment_method(card_number: str, user: User = Depends(jwt_auth)):
    await PaymentMethod.filter(user=user, card_number=card_number).delete()
    await RedisCache.delete("payment_methods", user.id)


@router.post("/devices", status_code=204)
async def add_mobile_device_for_push(data: AddPushDeviceData, user: User = Depends(jwt_auth)):
    await UserDevice.get_or_create(user=user, device_token=data.device_token)
