import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import AppUser
from tutoring.models import StudyDocument
from tutoring.document_agent import ANALYSIS_VERSION
from tutoring.document_schemas import validate_document_analysis
from tutoring.document_analysis_service import (
    claim_document_analysis,
    fail_document_analysis,
    finish_document_analysis,
    get_saved_analysis,
)


class DocumentAnalysisServiceTests(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"BEDROCK_MODEL_ID": "test-model"})
        env.start()
        self.addCleanup(env.stop)

        self.owner = AppUser.objects.create(
            google_sub="analysis-owner",
            email="analysis-owner@example.com",
        )
        self.other = AppUser.objects.create(
            google_sub="analysis-other",
            email="analysis-other@example.com",
        )
        self.document = StudyDocument.objects.create(
            user=self.owner,
            filename="notes.txt",
            stored_path="uploads/notes.txt",
            status="ready",
            total_pages=1,
            pages_processed=1,
            chunks=[{"id": 0, "page": 1, "text": "Learning rate sets step size."}],
        )
        self.result = validate_document_analysis(
            {
                "overview": "Notes on learning rate.",
                "concepts": [{
                    "title": "Learning rate",
                    "description": "Controls step size.",
                    "supporting_chunk_ids": [0],
                }],
            },
            self.document.chunks,
            1,
        )
        self.result["analysis_version"] = ANALYSIS_VERSION
        self.result["coverage"] = {
            "chunk_ids": [0],
            "pages": [1],
            "extraction_status": "ready",
            "scope": "all_persisted_chunks",
        }

    def claim(self):
        return claim_document_analysis(
            self.document.id, user_id=self.owner.id
        )

    def finish(self, claim, result=None):
        return finish_document_analysis(
            self.document.id,
            user_id=self.owner.id,
            claim_token=claim["claim_token"],
            source_hash=claim["source_hash"],
            model_id=claim["model_id"],
            result=self.result if result is None else result,
        )

    def test_save_and_reuse(self):
        claim = self.claim()
        self.assertEqual(claim["state"], "claimed")
        self.assertTrue(self.finish(claim))
        self.assertEqual(self.claim()["state"], "cached")
        self.assertEqual(
            get_saved_analysis(self.document.id, user_id=self.owner.id),
            self.result,
        )

    def test_active_claim_blocks_second_request(self):
        self.assertEqual(self.claim()["state"], "claimed")
        self.assertEqual(self.claim()["state"], "busy")

    def test_other_user_cannot_read_or_claim(self):
        for operation in (get_saved_analysis, claim_document_analysis):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(PermissionError):
                    operation(self.document.id, user_id=self.other.id)
        self.document.refresh_from_db()
        self.assertEqual(self.document.analysis_status, "pending")

    def test_expired_worker_cannot_overwrite_new_claim(self):
        old = self.claim()
        StudyDocument.objects.filter(id=self.document.id).update(
            analysis_started_at=timezone.now() - timedelta(minutes=16)
        )
        new = self.claim()
        self.assertEqual(new["state"], "claimed")
        self.assertNotEqual(old["claim_token"], new["claim_token"])
        self.assertFalse(self.finish(old))
        self.assertFalse(fail_document_analysis(
            self.document.id,
            user_id=self.owner.id,
            claim_token=old["claim_token"],
        ))
        self.assertTrue(self.finish(new))

    def test_changed_source_invalidates_saved_analysis(self):
        self.assertTrue(self.finish(self.claim()))
        StudyDocument.objects.filter(id=self.document.id).update(
            chunks=[{"id": 0, "page": 1, "text": "Updated source text."}]
        )
        self.assertIsNone(
            get_saved_analysis(self.document.id, user_id=self.owner.id)
        )
        self.assertEqual(self.claim()["state"], "claimed")

    def test_changed_model_invalidates_saved_analysis(self):
        self.assertTrue(self.finish(self.claim()))
        with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "different-model"}):
            self.assertIsNone(
                get_saved_analysis(self.document.id, user_id=self.owner.id)
            )

    def test_tampered_pages_are_not_saved(self):
        claim = self.claim()
        self.result["concepts"][0]["pages"] = [99]
        with self.assertRaises(ValueError):
            self.finish(claim)
        self.document.refresh_from_db()
        self.assertEqual(self.document.analysis, {})

    def test_failure_releases_claim_for_retry(self):
        claim = self.claim()
        self.assertTrue(fail_document_analysis(
            self.document.id,
            user_id=self.owner.id,
            claim_token=claim["claim_token"],
        ))
        self.document.refresh_from_db()
        self.assertEqual(self.document.analysis_status, "failed")
        self.assertIsNone(self.document.analysis_claim_token)
        self.assertEqual(self.claim()["state"], "claimed")
