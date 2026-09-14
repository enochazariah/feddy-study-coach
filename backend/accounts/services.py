from django.utils import timezone

from .google_auth import GoogleProfile
from .models import AppUser


def find_or_create_user(profile: GoogleProfile) -> AppUser:
    user, created = AppUser.objects.get_or_create(
        google_sub=profile.sub,
        defaults={
            "email": profile.email,
            "display_name": profile.name,
            "avatar_url": profile.picture,
        },
    )
    if not created:
        user.last_login_at = timezone.now()
        user.save(update_fields=["last_login_at"])
    else:
        user.last_login_at = timezone.now()
        user.save(update_fields=["last_login_at"])

    return user
