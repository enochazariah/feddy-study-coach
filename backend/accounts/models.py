import uuid

from django.db import models


class AppUser(models.Model):
    """
    Deliberately not Django's built-in auth.User: this system has no password
    authentication at all (Part III.1), so we don't want a password field sitting
    unused waiting to be misused later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    google_sub = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255, null=True, blank=True)
    avatar_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.email
