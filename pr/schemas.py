from pydantic import BaseModel, EmailStr


class LoginData(BaseModel):
    email: EmailStr
    password: str
    captcha_key: str | None = None


class RegisterData(LoginData):
    first_name: str
    last_name: str
