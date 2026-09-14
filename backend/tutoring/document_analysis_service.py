"""Owner-scoped lookup and reuse of persisted document analysis."""

import hashlib
import json
import os
import uuid

from .document_agent import ANALYSIS_VERSION
from .models import StudyDocument


def get_owned_document(document_id, *, user_id):
    if user_id is None:
        raise PermissionError("Document not found.")
    try:
        parsed_id = uuid.UUID(str(document_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid document reference.") from exc

    document = StudyDocument.objects.filter(
        id=parsed_id, user_id=user_id
    ).first()
    if document is None:
        raise PermissionError("Document not found.")
    return document


def source_fingerprint(document):
    """Hash the source content and extraction metadata used by analysis."""
    payload = {
        "chunks": document.chunks,
        "status": document.status,
        "total_pages": document.total_pages,
        "pages_processed": document.pages_processed,
    }
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def configured_model_id():
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id or not model_id.strip():
        raise RuntimeError("BEDROCK_MODEL_ID is required.")
    return model_id


def analysis_is_current(document, *, source_hash, model_id):
    return (
        document.analysis_status == "ready"
        and document.analysis_version == ANALYSIS_VERSION
        and document.analysis_source_hash == source_hash
        and document.analysis_model_id == model_id
        and isinstance(document.analysis, dict)
        and document.analysis.get("analysis_version") == ANALYSIS_VERSION
        and isinstance(document.analysis.get("overview"), str)
        and bool(document.analysis["overview"].strip())
        and isinstance(document.analysis.get("concepts"), list)
        and isinstance(document.analysis.get("coverage"), dict)
    )


def get_saved_analysis(document_id, *, user_id):
    """Return current persisted analysis, or None. Never invoke a model."""
    document = get_owned_document(document_id, user_id=user_id)
    if analysis_is_current(
        document,
        source_hash=source_fingerprint(document),
        model_id=configured_model_id(),
    ):
        return document.analysis
    return None


ANALYSIS_CLAIM_SECONDS = 900


def claim_document_analysis(document_id, *, user_id):
    """Return cached, busy, or claimed using an atomic conditional update."""
    from datetime import timedelta
    from django.utils import timezone

    document = get_owned_document(document_id, user_id=user_id)
    model_id = configured_model_id()
    source_hash = source_fingerprint(document)

    if analysis_is_current(
        document, source_hash=source_hash, model_id=model_id
    ):
        return {"state": "cached", "analysis": document.analysis}

    if document.status == "failed" or not document.chunks:
        raise ValueError("No readable document text is available.")

    now = timezone.now()
    cutoff = now - timedelta(seconds=ANALYSIS_CLAIM_SECONDS)
    if (
        document.analysis_status == "processing"
        and document.analysis_started_at is not None
        and document.analysis_started_at > cutoff
    ):
        return {"state": "busy"}

    token = uuid.uuid4()

    # Compare the state we read before updating. If another request changes
    # it first, this update affects zero rows and this request must not run.
    updated = StudyDocument.objects.filter(
        id=document.id,
        user_id=user_id,
        analysis_status=document.analysis_status,
        analysis_claim_token=document.analysis_claim_token,
        analysis_started_at=document.analysis_started_at,
        analysis_completed_at=document.analysis_completed_at,
        analysis_version=document.analysis_version,
        analysis_source_hash=document.analysis_source_hash,
        analysis_model_id=document.analysis_model_id,
    ).update(
        analysis_status="processing",
        analysis_claim_token=token,
        analysis_started_at=now,
        analysis_completed_at=None,
        analysis_error="",
        analysis_version=ANALYSIS_VERSION,
        analysis_source_hash=source_hash,
        analysis_model_id=model_id,
    )

    if updated != 1:
        return {"state": "busy"}

    return {
        "state": "claimed",
        "document": document,
        "claim_token": token,
        "source_hash": source_hash,
        "model_id": model_id,
    }


def _active_claim(document_id, *, user_id, claim_token):
    """Select only the processing job identified by this exact token."""
    token = uuid.UUID(str(claim_token))
    return StudyDocument.objects.filter(
        id=document_id,
        user_id=user_id,
        analysis_status="processing",
        analysis_claim_token=token,
    )


def finish_document_analysis(
    document_id, *, user_id, claim_token, source_hash, model_id, result
):
    """Validate and save a result only while this worker owns the claim."""
    from django.utils import timezone
    from .document_schemas import validate_document_analysis

    document = get_owned_document(document_id, user_id=user_id)
    if source_fingerprint(document) != source_hash:
        raise ValueError("Document source changed during analysis.")
    if not isinstance(result, dict):
        raise ValueError("Analysis result must be an object.")

    # Revalidate the semantic fields and recompute IDs/pages before saving.
    try:
        output = {
            "overview": result["overview"],
            "concepts": [
                {
                    "title": concept["title"],
                    "description": concept["description"],
                    "supporting_chunk_ids": concept["supporting_chunk_ids"],
                }
                for concept in result["concepts"]
            ],
        }
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed analysis result.") from exc

    normalized = validate_document_analysis(
        output, document.chunks, document.total_pages
    )
    normalized["analysis_version"] = ANALYSIS_VERSION
    normalized["coverage"] = {
        "chunk_ids": [chunk["id"] for chunk in document.chunks],
        "pages": sorted({chunk["page"] for chunk in document.chunks}),
        "extraction_status": document.status,
        "scope": "all_persisted_chunks",
    }
    if result != normalized:
        raise ValueError("Analysis metadata or source references are inconsistent.")

    updated = _active_claim(
        document_id, user_id=user_id, claim_token=claim_token
    ).filter(
        analysis_source_hash=source_hash,
        analysis_model_id=model_id,
        analysis_version=ANALYSIS_VERSION,
        chunks=document.chunks,
        status=document.status,
        total_pages=document.total_pages,
        pages_processed=document.pages_processed,
    ).update(
        analysis=normalized,
        analysis_status="ready",
        analysis_completed_at=timezone.now(),
        analysis_claim_token=None,
        analysis_error="",
    )
    return updated == 1


def fail_document_analysis(document_id, *, user_id, claim_token):
    """Record a generic failure without persisting provider errors or secrets."""
    from django.utils import timezone

    updated = _active_claim(
        document_id, user_id=user_id, claim_token=claim_token
    ).update(
        analysis_status="failed",
        analysis_completed_at=timezone.now(),
        analysis_claim_token=None,
        analysis_error="Document analysis could not be completed.",
    )
    return updated == 1
