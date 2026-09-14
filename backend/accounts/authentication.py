import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import AppUser
from .tokens import verify_session_token


class _AuthenticatedAppUser:
    """
    Thin wrapper so DRF's IsAuthenticated permission (which checks
    `request.user.is_authenticated`) works against our AppUser model,
    which is intentionally not Django's built-in auth.User.
    """

    is_authenticated = True

    def __init__(self, app_user: AppUser):
        self.app_user = app_user
        self.id = app_user.id
        self.pk = app_user.id  # django-ratelimit's "user" key reads request.user.pk


class SessionTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None  # No credentials supplied — let DRF's permission classes reject as needed.

        token = header[len("Bearer ") :]

        try:
            user_id = verify_session_token(token)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid or expired session") from exc

        try:
            app_user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist as exc:
            raise AuthenticationFailed("User not found") from exc

        return (_AuthenticatedAppUser(app_user), token)
