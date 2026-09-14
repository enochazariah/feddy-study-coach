import jwt
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import AppUser
from accounts.tokens import issue_session_token, verify_session_token


class SessionTokenTests(TestCase):
    def test_issue_and_verify_round_trip(self):
        token = issue_session_token("some-user-id")
        self.assertEqual(verify_session_token(token), "some-user-id")

    def test_garbage_token_raises(self):
        with self.assertRaises(jwt.InvalidTokenError):
            verify_session_token("not.a.jwt")


class AuthenticatedEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = AppUser.objects.create(
            google_sub="test-sub", email="student@example.com", display_name="Test Student"
        )
        self.token = issue_session_token(str(self.user.id))

    def test_me_requires_authentication(self):
        response = self.client.get("/api/user/me")
        self.assertEqual(response.status_code, 403)

    def test_me_rejects_invalid_token(self):
        response = self.client.get("/api/user/me", HTTP_AUTHORIZATION="Bearer garbage")
        self.assertEqual(response.status_code, 403)

    def test_me_returns_authenticated_user(self):
        response = self.client.get("/api/user/me", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "student@example.com")

    def test_subjects_requires_authentication(self):
        response = self.client.get("/api/subjects")
        self.assertEqual(response.status_code, 403)

    def test_tutor_chat_requires_authentication(self):
        response = self.client.post(
            "/api/tutor/chat", {"message": "hi", "mode": "standard"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
