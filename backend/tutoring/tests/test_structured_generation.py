from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from tutoring.document_feedback import ConceptFeedbackOutput, assess_explanation
from tutoring.document_lessons import DocumentLessonOutput, generate_selected_lesson
from tutoring.quiz_generator import _run_structured, evaluate_theory_with_bedrock
from tutoring.quiz_schemas import MultipleChoiceBatch, TheoryEvaluation


class StructuredGenerationTests(TestCase):
    def setUp(self):
        self.agent_patch = patch("strands.Agent")
        self.agent_factory = self.agent_patch.start()
        self.addCleanup(self.agent_patch.stop)

        self.model_patches = [
            patch("tutoring.document_lessons.create_bedrock_model"),
            patch("tutoring.document_feedback.create_bedrock_model"),
            patch("tutoring.quiz_generator.create_bedrock_model"),
        ]
        for model_patch in self.model_patches:
            model_patch.start()
            self.addCleanup(model_patch.stop)

        self.chunks = [{
            "id": 0,
            "page": 2,
            "text": "Learning rate controls step size.",
        }]

    def set_result(self, *, stop_reason="tool_use", structured_output=None):
        self.agent_factory.return_value.return_value = SimpleNamespace(
            stop_reason=stop_reason,
            structured_output=structured_output,
        )

    def test_lesson_accepts_tool_use_structured_completion_and_sources(self):
        self.set_result(
            structured_output=DocumentLessonOutput(
                explanation="The learning rate controls each update's size.",
                example="A smaller rate makes smaller updates.",
                key_ideas=["Step size"],
                questions=["How does the rate affect updates?"],
                supporting_chunk_ids=[0],
            )
        )

        result = generate_selected_lesson(
            topic="Learning rate",
            chunks=self.chunks,
        )

        self.assertEqual(result["sources"], [2])
        self.assertEqual(
            self.agent_factory.return_value.call_args.kwargs[
                "structured_output_model"
            ],
            DocumentLessonOutput,
        )

    def test_feedback_accepts_tool_use_structured_completion_and_sources(self):
        self.set_result(
            structured_output=ConceptFeedbackOutput(
                feedback="Your explanation identifies the role of step size.",
                demonstrated_strengths=["Defines the update size"],
                likely_gaps=[],
                recommended_next_action="Compare two learning rates.",
                next_question="What happens when the rate is too large?",
                supporting_chunk_ids=[0],
            )
        )

        result = assess_explanation(
            topic="Learning rate",
            answer="It controls the step size.",
            chunks=self.chunks,
        )

        self.assertEqual(result["sources"], [2])
        self.assertEqual(
            self.agent_factory.return_value.call_args.kwargs[
                "structured_output_model"
            ],
            ConceptFeedbackOutput,
        )

    def test_quiz_accepts_tool_use_structured_completion(self):
        output = MultipleChoiceBatch.model_validate({
            "questions": [{
                "question": "What does the learning rate control?",
                "options": ["Step size", "Page count", "File type", "Topic name"],
                "answer": "Step size",
                "explanation": "It controls the size of each update.",
            }],
        })
        self.set_result(structured_output=output)

        result = _run_structured(
            name="Test quiz",
            instructions="Return a quiz.",
            payload={"topic": "Learning rate"},
            schema=MultipleChoiceBatch,
            max_tokens=100,
        )

        self.assertEqual(result.questions[0].answer, "Step size")

    def test_structured_runner_rejects_missing_output(self):
        self.set_result(structured_output=None)

        with self.assertRaisesRegex(ValueError, "no valid structured output"):
            _run_structured(
                name="Test quiz",
                instructions="Return a quiz.",
                payload={"topic": "Learning rate"},
                schema=MultipleChoiceBatch,
                max_tokens=100,
            )

    def test_structured_runner_rejects_invalid_output(self):
        self.set_result(structured_output={"questions": []})

        with self.assertRaisesRegex(ValueError, "no valid structured output"):
            _run_structured(
                name="Test quiz",
                instructions="Return a quiz.",
                payload={"topic": "Learning rate"},
                schema=MultipleChoiceBatch,
                max_tokens=100,
            )

    def test_structured_runner_rejects_unsuccessful_termination(self):
        self.set_result(
            stop_reason="limit_turns",
            structured_output=MultipleChoiceBatch.model_validate({
                "questions": [{
                    "question": "What does the learning rate control?",
                    "options": ["Step size", "Page count", "File type", "Topic name"],
                    "answer": "Step size",
                    "explanation": "It controls the size of each update.",
                }],
            }),
        )

        with self.assertRaisesRegex(ValueError, "did not complete"):
            _run_structured(
                name="Test quiz",
                instructions="Return a quiz.",
                payload={"topic": "Learning rate"},
                schema=MultipleChoiceBatch,
                max_tokens=100,
            )

    def test_theory_evaluation_calculates_score_and_renders_deductions(self):
        output = TheoryEvaluation.model_validate({
            "criteria": [
                {
                    "criterion": "Update rule",
                    "maximum_points": 25,
                    "awarded_points": 25,
                    "feedback": "Correctly explains the update.",
                },
                {
                    "criterion": "Stationarity versus minimality",
                    "maximum_points": 25,
                    "awarded_points": 20,
                    "feedback": "The claim that zero gradient always means a local minimum is incorrect.",
                },
                {
                    "criterion": "Learning-rate consequences",
                    "maximum_points": 25,
                    "awarded_points": 21,
                    "feedback": "Mostly correct consequences.",
                },
                {
                    "criterion": "Reasoning",
                    "maximum_points": 25,
                    "awarded_points": 15,
                    "feedback": "The explanation connects the main ideas.",
                },
            ],
            "feedback": "Keep distinguishing stationarity from minimality.",
        })
        with patch("tutoring.quiz_generator._run_structured", return_value=output) as runner:
            result = evaluate_theory_with_bedrock(
                response="My answer",
                question="Explain gradient descent and when zero gradient is enough.",
                model_answer="The model answer",
                rubric="Four criteria totaling 100 points.",
            )

        self.assertEqual(result["score"], 81)
        self.assertIn("Stationarity versus minimality: 20/25.", result["feedback"])
        self.assertIn("zero gradient always means a local minimum", result["feedback"])
        self.assertNotIn("Deducted 5 points", result["feedback"])
        payload = runner.call_args.kwargs["payload"]
        self.assertEqual(payload["question"], "Explain gradient descent and when zero gradient is enough.")
        self.assertEqual(runner.call_args.kwargs["max_tokens"], 3000)
        instructions = runner.call_args.kwargs["instructions"]
        for requirement in (
            "Inspect the entire learner answer",
            "Accept equivalent mathematical definitions",
            "single most relevant criterion",
            "Keep all numeric scores",
            "optional improvements as suggestions",
        ):
            self.assertIn(requirement, instructions)

    def test_theory_evaluation_rejects_invalid_criterion_bounds_and_totals(self):
        with self.assertRaises(ValidationError):
            TheoryEvaluation.model_validate({
                "criteria": [{
                    "criterion": "Correctness",
                    "maximum_points": 10,
                    "awarded_points": 11,
                    "feedback": "Too many points.",
                }],
                "feedback": "Review.",
            })
        with self.assertRaises(ValidationError):
            TheoryEvaluation.model_validate({
                "criteria": [{
                    "criterion": "Correctness",
                    "maximum_points": 99,
                    "awarded_points": 50,
                    "feedback": "Review.",
                }],
                "feedback": "Review.",
            })
