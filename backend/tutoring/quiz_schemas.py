"""Strict output contracts for quiz generation and theory grading."""

from typing import Annotated

from pydantic import (
    BaseModel, ConfigDict, Field, StrictInt, StringConstraints,
    model_validator,
)


QuestionText = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=2000
    ),
]
OptionText = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=600
    ),
]
ExplanationText = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=3000
    ),
]


class MultipleChoiceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: QuestionText
    options: list[OptionText] = Field(min_length=4, max_length=4)
    answer: OptionText
    explanation: ExplanationText

    @model_validator(mode="after")
    def validate_options_and_answer(self):
        normalized = [" ".join(option.casefold().split()) for option in self.options]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Answer options must be distinct.")
        if self.answer not in self.options:
            raise ValueError("Answer must exactly match one option.")
        return self


class TheoryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: QuestionText
    rubric: ExplanationText
    model_answer: ExplanationText


class MultipleChoiceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    questions: list[MultipleChoiceQuestion] = Field(min_length=1, max_length=10)


class TheoryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    questions: list[TheoryQuestion] = Field(min_length=1, max_length=10)


class TheoryCriterionEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criterion: QuestionText
    maximum_points: StrictInt = Field(ge=1, le=100)
    awarded_points: StrictInt = Field(ge=0, le=100)
    feedback: ExplanationText

    @model_validator(mode="after")
    def validate_awarded_points(self):
        if self.awarded_points > self.maximum_points:
            raise ValueError("Awarded points cannot exceed maximum points.")
        return self


class TheoryEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criteria: list[TheoryCriterionEvaluation] = Field(min_length=1, max_length=10)
    feedback: ExplanationText

    @model_validator(mode="after")
    def validate_total_maximum(self):
        if sum(item.maximum_points for item in self.criteria) != 100:
            raise ValueError("Criterion maximum points must total 100.")
        return self
