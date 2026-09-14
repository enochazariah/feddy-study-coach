from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from strands.types.exceptions import MaxTokensReachedException

from accounts.models import AppUser
from accounts.tokens import issue_session_token
from tutoring.models import EvaluationToken, LearningEvidence
from tutoring.views import _claim_evaluation_token, _new_evaluation_token


class EvaluationTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = AppUser.objects.create(
            google_sub="evaluation-owner",
            email="evaluation-owner@example.com",
        )
        self.other = AppUser.objects.create(
            google_sub="evaluation-other",
            email="evaluation-other@example.com",
        )
        self.authenticate(self.owner)

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {issue_session_token(str(user.id))}"
        )

    def generate(self, question_type="multiple_choice"):
        if question_type == "theory":
            question = {
                "question": "Explain the update.",
                "rubric": "Award points for correct reasoning.",
                "model_answer": "The update follows the gradient.",
            }
        else:
            question = {
                "question": "What is correct?",
                "options": ["A", "B", "C", "D"],
                "answer": "A",
                "explanation": "A is correct.",
            }
        original = question.copy()
        with patch("tutoring.views.generate_quiz", return_value=[question]):
            response = self.client.post(
                "/api/active-learning/generate/",
                {"topic": "Testing", "num_questions": 1, "question_type": question_type},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        return response.data["questions"][0], original

    def test_generation_returns_no_hidden_grading_payload(self):
        for question_type in ("multiple_choice", "theory"):
            with self.subTest(question_type=question_type):
                question, _ = self.generate(question_type)
                self.assertIn("evaluation_token", question)
                self.assertNotIn("answer", question)
                self.assertNotIn("explanation", question)
                self.assertNotIn("model_answer", question)
                self.assertNotIn("rubric", question)
                self.assertEqual(EvaluationToken.objects.count(), 1 if question_type == "multiple_choice" else 2)

    def test_objective_evaluation_is_deterministic_and_replay_is_rejected(self):
        question, _ = self.generate()
        first = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": question["evaluation_token"]},
            format="json",
        )
        second = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": question["evaluation_token"]},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["score"], 100)
        self.assertEqual(second.status_code, 403)
        self.assertIn("already graded", second.data["error"])
        self.assertEqual(EvaluationToken.objects.get().status, "consumed")
        self.assertEqual(LearningEvidence.objects.count(), 1)
        evidence = LearningEvidence.objects.get()
        self.assertEqual(evidence.question_type, "objective")
        self.assertEqual(evidence.submitted_answer, "A")
        self.assertEqual(evidence.score, 100)

    @patch("tutoring.views.evaluate_theory_with_bedrock")
    def test_theory_evaluation_uses_server_payload_and_consumes(self, grader):
        grader.return_value = {"score": 80, "feedback": "Good reasoning."}
        question, original = self.generate("theory")
        self.assertNotIn(original["model_answer"], str(question))
        self.assertNotIn(original["rubric"], str(question))
        response = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "My explanation", "evaluation_token": question["evaluation_token"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        grader.assert_called_once_with(
            response="My explanation",
            question=original["question"],
            model_answer=original["model_answer"],
            rubric=original["rubric"],
            user_id=str(self.owner.id),
        )
        self.assertEqual(EvaluationToken.objects.get().status, "consumed")
        self.assertEqual(LearningEvidence.objects.count(), 1)
        evidence = LearningEvidence.objects.get()
        self.assertEqual(evidence.topic, "Testing")
        self.assertEqual(evidence.question, original["question"])
        self.assertEqual(evidence.submitted_answer, "My explanation")
        self.assertEqual(evidence.score, 80)

    @patch("tutoring.views.evaluate_theory_with_bedrock")
    def test_legacy_theory_payload_without_question_fails_closed(self, grader):
        raw_token = _new_evaluation_token(
            user_id=self.owner.id,
            kind="theory",
            grading_payload={
                "model_answer": "The update follows the gradient.",
                "rubric": "Award points for correct reasoning.",
            },
        )
        response = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "My explanation", "evaluation_token": raw_token},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        grader.assert_not_called()
        self.assertEqual(EvaluationToken.objects.get().status, "issued")

    def test_wrong_owner_expired_invalid_and_legacy_tokens_are_rejected(self):
        question, _ = self.generate()
        self.authenticate(self.other)
        wrong_owner = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": question["evaluation_token"]},
            format="json",
        )
        self.assertEqual(wrong_owner.status_code, 403)
        self.assertIn("ownership", wrong_owner.data["error"])

        self.authenticate(self.owner)
        record = EvaluationToken.objects.get()
        record.expires_at = timezone.now() - timedelta(seconds=1)
        record.save(update_fields=["expires_at"])
        expired = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": question["evaluation_token"]},
            format="json",
        )
        self.assertEqual(expired.status_code, 403)
        self.assertIn("expired", expired.data["error"])

        invalid = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": "not-a-token"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 403)
        self.assertIn("Generate a new quiz", invalid.data["error"])

        legacy = signing.dumps(
            {"user_id": str(self.owner.id), "answer": "A", "explanation": "hidden"},
            salt="feddy-objective-evaluation",
        )
        legacy_response = self.client.post(
            "/api/tutor/active-learning/evaluate/",
            {"response": "A", "evaluation_token": legacy},
            format="json",
        )
        self.assertEqual(legacy_response.status_code, 403)
        self.assertIn("Generate a new quiz", legacy_response.data["error"])

    def test_duplicate_claim_is_rejected(self):
        raw_token = _new_evaluation_token(
            user_id=self.owner.id,
            kind="objective",
            grading_payload={"answer": "A", "explanation": ""},
        )
        _claim_evaluation_token(raw_token=raw_token, user_id=self.owner.id)
        with self.assertRaisesRegex(ValueError, "already being graded"):
            _claim_evaluation_token(raw_token=raw_token, user_id=self.owner.id)

    @patch("tutoring.views.evaluate_theory_with_bedrock")
    def test_theory_failure_releases_claim_for_retry(self, grader):
        grader.side_effect = [RuntimeError("temporary"), {"score": 70, "feedback": "Recovered."}]
        question, _ = self.generate("theory")
        payload = {"response": "My explanation", "evaluation_token": question["evaluation_token"]}
        first = self.client.post("/api/tutor/active-learning/evaluate/", payload, format="json")
        second = self.client.post("/api/tutor/active-learning/evaluate/", payload, format="json")
        self.assertEqual(first.status_code, 503)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(EvaluationToken.objects.get().status, "consumed")
        self.assertEqual(LearningEvidence.objects.count(), 1)

    @patch("tutoring.views.evaluate_theory_with_bedrock")
    def test_theory_max_tokens_failure_returns_retryable_error(self, grader):
        grader.side_effect = MaxTokensReachedException("structured output truncated")
        question, _ = self.generate("theory")
        payload = {
            "response": "My complete explanation",
            "evaluation_token": question["evaluation_token"],
        }

        first = self.client.post(
            "/api/tutor/active-learning/evaluate/", payload, format="json"
        )

        self.assertEqual(first.status_code, 503)
        self.assertIn("temporarily unavailable", first.data["error"])
        self.assertNotIn("score", first.data)
        self.assertEqual(EvaluationToken.objects.get().status, "issued")
        self.assertEqual(LearningEvidence.objects.count(), 0)
