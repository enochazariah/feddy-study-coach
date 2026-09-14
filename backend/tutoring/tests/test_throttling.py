from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import AppUser
from accounts.tokens import issue_session_token
from tutoring.views import (
    ChatRateThrottle,
    EvaluationRateThrottle,
    QuizRateThrottle,
    ResearchRateThrottle,
    UploadRateThrottle,
)


TEST_REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "upload": "20/hour",
        "research": "60/hour",
        "chat": "2/minute",
        "quiz": "20/hour",
        "evaluation": "30/hour",
    },
}



class ProductionThrottleRateTests(TestCase):
    def test_named_throttles_resolve_production_rates(self):
        expected = {
            UploadRateThrottle: "20/hour",
            ResearchRateThrottle: "60/hour",
            ChatRateThrottle: "60/hour",
            QuizRateThrottle: "20/hour",
            EvaluationRateThrottle: "30/hour",
        }
        for throttle_class, rate in expected.items():
            assert throttle_class().get_rate() == rate


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "feddy-throttle-tests",
        }
    },
    REST_FRAMEWORK=TEST_REST_FRAMEWORK,
)
class ThrottlingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.chat_rate_patch = patch.object(ChatRateThrottle, "get_rate", return_value="2/minute")
        self.chat_rate_patch.start()
        self.addCleanup(self.chat_rate_patch.stop)
        self.addCleanup(cache.clear)
        self.client = APIClient()
        self.users = [
            AppUser.objects.create(
                google_sub=f"throttle-user-{index}",
                email=f"throttle{index}@example.com",
                display_name=f"Throttle User {index}",
            )
            for index in range(2)
        ]

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {issue_session_token(str(user.id))}"
        )

    @patch("tutoring.views.run_tutor", return_value="mocked response")
    def test_small_test_limit_returns_429_without_invoking_tutor(self, tutor_mock):
        self.authenticate(self.users[0])
        for _ in range(2):
            response = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
            assert response.status_code == 200
        response = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
        assert response.status_code == 429
        assert tutor_mock.call_count == 2

    @patch("tutoring.views.run_tutor", return_value="mocked response")
    def test_rejected_chat_does_not_save_messages(self, tutor_mock):
        self.authenticate(self.users[0])
        for _ in range(2):
            self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
        from tutoring.models import Conversation, Message
        conversations_before = Conversation.objects.filter(user=self.users[0]).count()
        messages_before = Message.objects.filter(conversation__user=self.users[0]).count()
        response = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
        assert response.status_code == 429
        assert tutor_mock.call_count == 2
        assert Conversation.objects.filter(user=self.users[0]).count() == conversations_before
        assert Message.objects.filter(conversation__user=self.users[0]).count() == messages_before

    @patch("tutoring.views.run_tutor", return_value="mocked response")
    def test_different_users_have_separate_allowances(self, tutor_mock):
        for user in self.users:
            self.authenticate(user)
            for _ in range(2):
                response = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
                assert response.status_code == 200
            response = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
            assert response.status_code == 429
        assert tutor_mock.call_count == 4

    @patch("tutoring.views.run_tutor", return_value="mocked response")
    def test_chat_aliases_share_user_allowance(self, tutor_mock):
        self.authenticate(self.users[0])
        first = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
        second = self.client.post("/api/tutoring/chat/", {"message": "hello"}, format="json")
        third = self.client.post("/api/tutor/chat/", {"message": "hello"}, format="json")
        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert tutor_mock.call_count == 2