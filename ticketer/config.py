import warnings
from base64 import b64decode
from os import environ

from aiofcm import FCM
from s3lite import Client

OAUTH_GOOGLE_CLIENT_ID = environ["OAUTH_GOOGLE_CLIENT_ID"]
OAUTH_GOOGLE_CLIENT_SECRET = environ["OAUTH_GOOGLE_CLIENT_SECRET"]
OAUTH_GOOGLE_REDIRECT = "http://127.0.0.1:8000/auth/google/callback"

FCM_API_ID = int(environ.get("FCM_API_ID", 0))
FCM_API_KEY = environ.get("FCM_API_KEY")

JWT_KEY = b64decode(environ["JWT_KEY"])

TURNSTILE_SITEKEY = "1x00000000000000000000AA"  # Always passes, visible
TURNSTILE_SECRET = "1x0000000000000000000000000000000AA"  # Always passes,
# 2x0000000000000000000000000000000AA always fails

DB_CONNECTION_STRING = environ.get("DB_CONNECTION_STRING", "sqlite://ticketer.db")

S3_ACCESS_KEY_ID = environ.get("S3_ACCESS_KEY_ID", None)
S3_SECRET_ACCESS_KEY = environ.get("S3_SECRET_ACCESS_KEY", None)
S3_ENDPOINT = environ.get("S3_ENDPOINT", None)

if S3_ACCESS_KEY_ID is not None and S3_SECRET_ACCESS_KEY is not None and S3_ENDPOINT is not None:
    S3 = Client(S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_ENDPOINT)
else:  # pragma: no cover
    S3 = None
    warnings.warn(
        "Some of s3 credentials not provided. Images (event images and avatars) uploading support is disabled!"
    )

fcm = FCM(FCM_API_ID, FCM_API_KEY)

PAYPAL_ID = environ.get("PAYPAL_ID")
PAYPAL_SECRET = environ.get("PAYPAL_SECRET")
