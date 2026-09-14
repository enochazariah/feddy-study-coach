from dataclasses import dataclass

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


@dataclass
class GoogleProfile:
    sub: str
    email: str
    name: str | None
    picture: str | None


def verify_google_id_token(raw_token: str) -> GoogleProfile:
    """
    Verifies a Google ID token directly with Google. We never trust a
    client-asserted email/name — everything here comes from the verified payload.
    """
    payload = id_token.verify_oauth2_token(
        raw_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
    )

    if not payload.get("email_verified", False):
        raise ValueError("Google email is not verified")

    return GoogleProfile(
        sub=payload["sub"],
        email=payload["email"],
        name=payload.get("name"),
        picture=payload.get("picture"),
    )
