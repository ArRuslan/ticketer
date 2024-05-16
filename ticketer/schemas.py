from pydantic import BaseModel, EmailStr


class LoginData(BaseModel):
    email: EmailStr
    password: str
    captcha_key: str | None = None


class RegisterData(LoginData):
    first_name: str
    last_name: str


class GoogleOAuthData(BaseModel):
    code: str
    state: str | None = None


class EditProfileData(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None
    mfa_key: str | None = ""
    mfa_code: str | None = None
    new_password: str | None = None
    phone_number: int | None = None
