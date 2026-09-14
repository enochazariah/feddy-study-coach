from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from tutoring.document_agent import analyze_document
from tutoring.document_schemas import DocumentAnalysisOutput


class DocumentAgentTests(TestCase):
    def setUp(self):
        self.document = SimpleNamespace(
            user_id="owner",
            status="ready",
            total_pages=3,
            chunks=[
                {"id": 0, "page": 2, "text": "Learning rate controls step size."}
            ],
        )
        self.model_patch = patch(
            "tutoring.document_agent.create_bedrock_model"
        )
        self.model_factory = self.model_patch.start()
        self.addCleanup(self.model_patch.stop)

        self.agent_patch = patch("strands.Agent")
        self.agent_factory = self.agent_patch.start()
        self.addCleanup(self.agent_patch.stop)

        self.agent_factory.return_value.return_value = SimpleNamespace(
            stop_reason="tool_use",
            structured_output=DocumentAnalysisOutput(
                overview="Notes about learning rate.",
                concepts=[{
                    "title": "Learning rate",
                    "description": "Controls the size of an update.",
                    "supporting_chunk_ids": [0],
                }],
            ),
        )

    def test_valid_analysis_uses_saved_evidence_and_returns_pages(self):
        result = analyze_document(self.document, user_id="owner")
        self.assertEqual(result["concepts"][0]["pages"], [2])
        self.assertEqual(result["coverage"]["chunk_ids"], [0])
        self.model_factory.assert_called_once_with(
            max_tokens=4096, temperature=0.2
        )
        call = self.agent_factory.return_value.call_args
        self.assertIn("Learning rate controls step size.", call.args[0])
        self.assertIs(
            call.kwargs["structured_output_model"], DocumentAnalysisOutput
        )
        self.assertEqual(call.kwargs["limits"]["turns"], 3)

    def test_other_owner_is_rejected_before_model_creation(self):
        with self.assertRaises(PermissionError):
            analyze_document(self.document, user_id="other")
        self.model_factory.assert_not_called()
        self.agent_factory.assert_not_called()

    def test_oversized_document_is_rejected_before_model_creation(self):
        self.document.chunks[0]["text"] = "x" * 32001
        with self.assertRaisesRegex(ValueError, "batching is required"):
            analyze_document(self.document, user_id="owner")
        self.model_factory.assert_not_called()
        self.agent_factory.assert_not_called()

    def test_invented_source_is_rejected(self):
        self.agent_factory.return_value.return_value.structured_output = (
            DocumentAnalysisOutput(
                overview="Notes.",
                concepts=[{
                    "title": "Learning rate",
                    "description": "Controls updates.",
                    "supporting_chunk_ids": [99],
                }],
            )
        )
        with self.assertRaisesRegex(ValueError, "absent"):
            analyze_document(self.document, user_id="owner")

    def test_incomplete_run_is_rejected(self):
        self.agent_factory.return_value.return_value.stop_reason = "limit_turns"
        with self.assertRaisesRegex(ValueError, "did not finish"):
            analyze_document(self.document, user_id="owner")

    def test_missing_structured_output_is_rejected(self):
        self.agent_factory.return_value.return_value.structured_output = None
        with self.assertRaisesRegex(ValueError, "invalid output"):
            analyze_document(self.document, user_id="owner")

    def test_invalid_structured_output_is_rejected(self):
        self.agent_factory.return_value.return_value.structured_output = {
            "overview": "Notes.",
            "concepts": [],
        }
        with self.assertRaisesRegex(ValueError, "invalid output"):
            analyze_document(self.document, user_id="owner")
