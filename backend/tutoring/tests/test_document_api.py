import os
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.test import APIClient

from accounts.models import AppUser
from accounts.tokens import issue_session_token
from tutoring.models import StudyDocument
from tutoring.document_agent import ANALYSIS_VERSION
from tutoring.document_schemas import validate_document_analysis
from tutoring.document_analysis_service import claim_document_analysis
from tutoring.document_views import document_detail, document_analyze


urlpatterns = [
    path("documents/<uuid:document_id>/", document_detail),
    path("documents/<uuid:document_id>/analyze/", document_analyze),
]


@override_settings(
    ROOT_URLCONF=__name__,
    CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "feddy-document-api-tests",
    }},
)
class DocumentAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        env = patch.dict(os.environ, {"BEDROCK_MODEL_ID": "test-model"})
        env.start()
        self.addCleanup(env.stop)

        agent = patch("tutoring.document_views.analyze_document")
        self.agent = agent.start()
        self.addCleanup(agent.stop)

        self.owner = AppUser.objects.create(
            google_sub="api-owner", email="api-owner@example.com"
        )
        self.other = AppUser.objects.create(
            google_sub="api-other", email="api-other@example.com"
        )
        self.document = StudyDocument.objects.create(
            user=self.owner, filename="notes.txt",
            stored_path="uploads/notes.txt", status="ready",
            total_pages=1, pages_processed=1,
            chunks=[{"id": 0, "page": 1, "text": "Learning rate sets step size."}],
        )
        result = validate_document_analysis({
            "overview": "Learning rate notes.",
            "concepts": [{
                "title": "Learning rate",
                "description": "Controls step size.",
                "supporting_chunk_ids": [0],
            }],
        }, self.document.chunks, 1)
        result["analysis_version"] = ANALYSIS_VERSION
        result["coverage"] = {
            "chunk_ids": [0], "pages": [1],
            "extraction_status": "ready", "scope": "all_persisted_chunks",
        }
        self.agent.return_value = result
        self.client = APIClient()
        self.detail_url = f"/documents/{self.document.id}/"
        self.analyze_url = self.detail_url + "analyze/"
        self.authenticate(self.owner)

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {issue_session_token(str(user.id))}"
        )

    def test_analysis_is_saved_and_reused(self):
        first = self.client.post(self.analyze_url, {}, format="json")
        second = self.client.post(self.analyze_url, {}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.data["reused"])
        self.assertTrue(second.data["reused"])
        self.agent.assert_called_once()
        detail = self.client.get(self.detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["analysisStatus"], "ready")
        self.assertEqual(detail.data["analysis"], self.agent.return_value)

    def test_detail_never_generates_analysis(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["analysisStatus"], "pending")
        self.assertIsNone(response.data["analysis"])
        self.agent.assert_not_called()

    def test_unowned_and_missing_documents_return_same_404(self):
        self.authenticate(self.other)
        for method, suffix in (("get", ""), ("post", "analyze/")):
            with self.subTest(method=method):
                request = getattr(self.client, method)
                unowned = request(self.detail_url + suffix)
                missing = request(f"/documents/{uuid.uuid4()}/" + suffix)
                self.assertEqual(unowned.status_code, 404)
                self.assertEqual(missing.status_code, 404)
                self.assertEqual(unowned.data, missing.data)
        self.agent.assert_not_called()

    def test_unauthenticated_requests_are_rejected(self):
        self.client.credentials()
        self.assertIn(self.client.get(self.detail_url).status_code, (401, 403))
        self.assertIn(self.client.post(self.analyze_url).status_code, (401, 403))
        self.agent.assert_not_called()

    def test_active_claim_returns_202_without_generation(self):
        claim_document_analysis(self.document.id, user_id=self.owner.id)
        response = self.client.post(self.analyze_url, {}, format="json")
        self.assertEqual(response.status_code, 202)
        self.agent.assert_not_called()

    def test_model_failure_is_recorded_without_exposing_error(self):
        self.agent.side_effect = RuntimeError("private-provider-detail")
        response = self.client.post(self.analyze_url, {}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-provider-detail", str(response.data))
        self.document.refresh_from_db()
        self.assertEqual(self.document.analysis_status, "failed")
        self.assertIsNone(self.document.analysis_claim_token)

    def test_failed_extraction_is_rejected_without_generation(self):
        self.document.status = "failed"
        self.document.save(update_fields=["status"])
        response = self.client.post(self.analyze_url, {}, format="json")
        self.assertEqual(response.status_code, 409)
        self.agent.assert_not_called()
