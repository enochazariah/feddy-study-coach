import hashlib

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from .authentication import SessionTokenAuthentication
from .google_auth import verify_google_id_token
from .models import AppUser
from .serializers import AppUserSerializer
from .services import find_or_create_user
from .tokens import issue_session_token


@api_view(["POST"])
def google_sign_in(request):
    raw_token = request.data.get("id_token")
    if not raw_token:
        return Response({"error": "id_token is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = find_or_create_user(verify_google_id_token(raw_token))
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({"token": issue_session_token(str(user.id)), "user": AppUserSerializer(user).data})


@api_view(["POST"])
def demo_login(request):
    if not settings.DEBUG or not settings.ALLOW_DEMO_LOGIN:
        return Response({"error": "Demo login is disabled."}, status=status.HTTP_404_NOT_FOUND)
    email = str(request.data.get("email", "")).strip().lower()
    if email != settings.DEMO_LOGIN_EMAIL:
        return Response({"error": "Use the configured development demo account."}, status=status.HTTP_401_UNAUTHORIZED)
    google_sub = "demo-" + hashlib.sha256(settings.DEMO_LOGIN_EMAIL.encode("utf-8")).hexdigest()
    user, _ = AppUser.objects.get_or_create(
        google_sub=google_sub,
        defaults={"email": settings.DEMO_LOGIN_EMAIL, "display_name": "Feddy Demo"},
    )
    if user.email != settings.DEMO_LOGIN_EMAIL:
        return Response({"error": "Demo account configuration is inconsistent."}, status=status.HTTP_409_CONFLICT)
    return Response({"token": issue_session_token(str(user.id)), "user": AppUserSerializer(user).data})


@api_view(["GET"])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({"user": AppUserSerializer(request.user.app_user).data})


def agent(message: str) -> str:
    """Legacy bridge retained for callers that import the accounts agent."""
    from tutoring.tutor_agent import run_tutor
    return run_tutor(message)
