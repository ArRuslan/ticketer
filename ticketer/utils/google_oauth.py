from typing import TypedDict

from httpx import AsyncClient

from ticketer import config
from ticketer.exceptions import CustomBodyException


class GoogleOAuthResponse(TypedDict):
    id: str
    email: str
    given_name: str
    family_name: str


class GoogleOAuthToken(TypedDict):
    access_token: str
    refresh_token: str
    expires_in: int


async def authorize_google(code: str) -> tuple[GoogleOAuthResponse, GoogleOAuthToken]:
    data = {
        "code": code,
        "client_id": config.OAUTH_GOOGLE_CLIENT_ID,
        "client_secret": config.OAUTH_GOOGLE_CLIENT_SECRET,
        "redirect_uri": config.OAUTH_GOOGLE_REDIRECT,
        "grant_type": "authorization_code",
    }

    async with AsyncClient() as client:
        resp = await client.post("https://accounts.google.com/o/oauth2/token", json=data)
        if "error" in resp.json():
            raise CustomBodyException(code=400, body={"error_message": f"Error: {resp.json()['error']}"})
        token_data = resp.json()

        info_resp = await client.get("https://www.googleapis.com/oauth2/v1/userinfo",
                                     headers={"Authorization": f"Bearer {token_data['access_token']}"})
        return info_resp.json(), token_data
