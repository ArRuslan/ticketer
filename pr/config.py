from base64 import b64decode
from os import environ

OAUTH_GOOGLE_CLIENT_ID = environ["OAUTH_GOOGLE_CLIENT_ID"]
OAUTH_GOOGLE_CLIENT_SECRET = environ["OAUTH_GOOGLE_CLIENT_ID"]
OAUTH_GOOGLE_REDIRECT = "http://127.0.0.1:8000/auth/google/callback"

JWT_KEY = b64decode(environ["JWT_KEY"])
