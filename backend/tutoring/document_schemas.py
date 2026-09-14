"""Strict, evidence-bound schemas for future document semantic analysis.

A valid supporting chunk ID establishes source identity only. It does not prove
that a model-generated explanation is semantically supported by that source.
"""

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator


MAX_OVERVIEW_LENGTH = 2000
MAX_CONCEPTS = 50
MAX_CONCEPT_TITLE_LENGTH = 200
MAX_CONCEPT_DESCRIPTION_LENGTH = 1000
MAX_SUPPORTING_CHUNK_IDS = 32


class DocumentConceptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: StrictStr = Field(min_length=1, max_length=MAX_CONCEPT_TITLE_LENGTH)
    description: StrictStr = Field(min_length=1, max_length=MAX_CONCEPT_DESCRIPTION_LENGTH)
    supporting_chunk_ids: list[StrictInt] = Field(
        min_length=1,
        max_length=MAX_SUPPORTING_CHUNK_IDS,
    )

    @field_validator("title", "description")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value.strip()

    @field_validator("supporting_chunk_ids")
    @classmethod
    def reject_boolean_or_duplicate_ids(cls, value: list[int]) -> list[int]:
        if any(isinstance(chunk_id, bool) for chunk_id in value):
            raise ValueError("chunk IDs must be integers, not booleans")
        if len(set(value)) != len(value):
            raise ValueError("supporting chunk IDs must be unique")
        if any(chunk_id < 0 for chunk_id in value):
            raise ValueError("chunk IDs must be non-negative")
        return value


class DocumentAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    overview: StrictStr = Field(min_length=1, max_length=MAX_OVERVIEW_LENGTH)
    concepts: list[DocumentConceptOutput] = Field(max_length=MAX_CONCEPTS)

    @field_validator("overview")
    @classmethod
    def reject_blank_overview(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("overview must not be blank")
        return value.strip()


def _validate_evidence(chunks: list[dict[str, Any]], total_pages: int) -> dict[int, dict[str, Any]]:
    if isinstance(total_pages, bool) or not isinstance(total_pages, int) or total_pages < 0:
        raise ValueError("total_pages must be a non-negative integer")

    evidence_by_id: dict[int, dict[str, Any]] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("evidence chunks must be objects")
        chunk_id = chunk.get("id")
        if isinstance(chunk_id, bool) or not isinstance(chunk_id, int) or chunk_id < 0:
            raise ValueError("evidence chunk IDs must be unique non-negative integers")
        if chunk_id in evidence_by_id:
            raise ValueError("evidence chunk IDs must be unique")
        evidence_by_id[chunk_id] = chunk
    return evidence_by_id


def _concept_id(title: str, chunk_ids: list[int]) -> str:
    identity = f"{title.casefold()}|{','.join(str(chunk_id) for chunk_id in sorted(chunk_ids))}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"concept-{digest}"


def validate_document_analysis(
    model_output: Any,
    chunks: list[dict[str, Any]],
    total_pages: int,
) -> dict[str, Any]:
    """Validate and normalize model analysis against exact supplied evidence.

    Supporting chunk IDs establish source identity only; they are not proof that
    a model explanation is semantically supported by the referenced text.
    """
    analysis = DocumentAnalysisOutput.model_validate(model_output)
    evidence_by_id = _validate_evidence(chunks, total_pages)
    normalized_concepts = []
    seen_concept_ids = set()

    for concept in analysis.concepts:
        supporting_chunks = [evidence_by_id.get(chunk_id) for chunk_id in concept.supporting_chunk_ids]
        if any(chunk is None for chunk in supporting_chunks):
            raise ValueError("concept references a chunk absent from supplied evidence")

        pages = set()
        for chunk in supporting_chunks:
            text = chunk.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("referenced chunks must contain nonblank text")
            page = chunk.get("page")
            if isinstance(page, bool) or not isinstance(page, int):
                raise ValueError("referenced chunks must have integer pages")
            if page < 1 or page > total_pages:
                raise ValueError("referenced chunk page is outside total_pages")
            pages.add(page)

        chunk_ids = list(concept.supporting_chunk_ids)
        concept_id = _concept_id(concept.title, chunk_ids)
        if concept_id in seen_concept_ids:
            raise ValueError("duplicate concept identity")
        seen_concept_ids.add(concept_id)
        normalized_concepts.append(
            {
                "id": concept_id,
                "title": concept.title,
                "description": concept.description,
                "supporting_chunk_ids": chunk_ids,
                "pages": sorted(pages),
            }
        )

    return {
        "overview": analysis.overview,
        "concepts": normalized_concepts,
    }
