from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

ALGORITHM = "HS256"


def issue_session_token(user_id: str) -> str:
    payload = {
        "user_id": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SESSION_JWT_SECRET, algorithm=ALGORITHM)


def verify_session_token(token: str) -> str:
    """Returns the user_id encoded in the token, or raises jwt.InvalidTokenError."""
    payload = jwt.decode(token, settings.SESSION_JWT_SECRET, algorithms=[ALGORITHM])
    return payload["user_id"]
