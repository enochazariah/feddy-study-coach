from rest_framework import serializers

from .models import AppUser


class AppUserSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name", allow_null=True)
    avatarUrl = serializers.URLField(source="avatar_url", allow_null=True)

    class Meta:
        model = AppUser
        fields = ["id", "email", "displayName", "avatarUrl"]
