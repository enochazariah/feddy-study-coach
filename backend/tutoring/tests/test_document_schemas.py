from unittest import TestCase

from pydantic import ValidationError

from tutoring.document_schemas import validate_document_analysis


class DocumentSchemaTests(TestCase):
    def setUp(self):
        self.chunks = [
            {"id": 0, "page": 2, "text": "Thought changes how a person acts."},
            {"id": 1, "page": 5, "text": "Purpose gives effort a direction."},
            {"id": 2, "page": 8, "text": "Health is affected by repeated thought."},
        ]

    def valid_output(self):
        return {
            "overview": "The document connects thought, purpose, health, and action.",
            "concepts": [
                {
                    "title": "Thought and purpose",
                    "description": "Purpose directs repeated thought into action.",
                    "supporting_chunk_ids": [1, 0],
                }
            ],
        }

    def test_valid_output_derives_sorted_pages_and_deterministic_id(self):
        result = validate_document_analysis(self.valid_output(), self.chunks, total_pages=8)
        concept = result["concepts"][0]
        self.assertEqual(concept["pages"], [2, 5])
        self.assertEqual(concept["supporting_chunk_ids"], [1, 0])
        self.assertEqual(concept["id"], "concept-" + concept["id"].split("concept-", 1)[1])
        self.assertEqual(result, validate_document_analysis(self.valid_output(), self.chunks, 8))

    def test_multiple_supporting_pages_are_unique_and_sorted(self):
        output = self.valid_output()
        output["concepts"][0]["supporting_chunk_ids"] = [2, 0, 1]
        result = validate_document_analysis(output, self.chunks, 8)
        self.assertEqual(result["concepts"][0]["pages"], [2, 5, 8])

    def test_unknown_chunk_id_is_rejected(self):
        output = self.valid_output()
        output["concepts"][0]["supporting_chunk_ids"] = [99]
        with self.assertRaises(ValueError):
            validate_document_analysis(output, self.chunks, 8)

    def test_duplicate_evidence_chunk_ids_are_rejected(self):
        duplicate_chunks = [
            {"id": 0, "page": 1, "text": "First source."},
            {"id": 0, "page": 2, "text": "Duplicate source ID."},
        ]
        with self.assertRaises(ValueError):
            validate_document_analysis(self.valid_output(), duplicate_chunks, 8)

    def test_boolean_evidence_chunk_ids_are_rejected(self):
        invalid_chunks = [{"id": True, "page": 1, "text": "Source."}]
        with self.assertRaises(ValueError):
            validate_document_analysis(self.valid_output(), invalid_chunks, 1)

    def test_invalid_page_is_rejected(self):
        chunks = [{"id": 0, "page": 9, "text": "Readable source."}]
        with self.assertRaises(ValueError):
            validate_document_analysis(self.valid_output() | {"concepts": [{**self.valid_output()["concepts"][0], "supporting_chunk_ids": [0]}]}, chunks, 8)

    def test_wrong_types_are_rejected(self):
        output = self.valid_output()
        output["concepts"][0]["supporting_chunk_ids"] = [True]
        with self.assertRaises((ValidationError, ValueError)):
            validate_document_analysis(output, self.chunks, 8)

    def test_empty_references_are_rejected(self):
        output = self.valid_output()
        output["concepts"][0]["supporting_chunk_ids"] = []
        with self.assertRaises(ValidationError):
            validate_document_analysis(output, self.chunks, 8)

    def test_extra_fields_are_rejected(self):
        output = self.valid_output()
        output["document_owner"] = "someone"
        with self.assertRaises(ValidationError):
            validate_document_analysis(output, self.chunks, 8)

    def test_blank_text_is_rejected(self):
        output = self.valid_output()
        output["overview"] = "   "
        with self.assertRaises(ValidationError):
            validate_document_analysis(output, self.chunks, 8)

    def test_noise_only_material_can_have_zero_concepts(self):
        result = validate_document_analysis(
            {"overview": "Only archive metadata was readable.", "concepts": []},
            [{"id": 0, "page": 1, "text": "Archive metadata only."}],
            1,
        )
        self.assertEqual(result["concepts"], [])

    def test_duplicate_concept_identity_is_rejected(self):
        for title, chunk_ids in (
            ("Thought and purpose", [1, 0]),
            ("THOUGHT AND PURPOSE", [0, 1]),
        ):
            with self.subTest(title=title, chunk_ids=chunk_ids):
                output = self.valid_output()
                duplicate = dict(output["concepts"][0])
                duplicate["title"] = title
                duplicate["supporting_chunk_ids"] = chunk_ids
                output["concepts"].append(duplicate)
                with self.assertRaisesRegex(ValueError, "duplicate concept identity"):
                    validate_document_analysis(output, self.chunks, 8)
