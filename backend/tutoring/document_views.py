"""Document detail and semantic-analysis API handlers."""

import logging
from django.db.models import F
from django.utils import timezone

from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.authentication import SessionTokenAuthentication
from .document_agent import analyze_document
from .document_analysis_service import (
    analysis_is_current,
    claim_document_analysis,
    configured_model_id,
    fail_document_analysis,
    finish_document_analysis,
    get_owned_document,
    source_fingerprint,
)
from .views import QuizRateThrottle, EvaluationRateThrottle
from .document_feedback import assess_explanation
from .models import LearnerConceptState

logger = logging.getLogger(__name__)


@api_view(["GET"])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def document_detail(request, document_id):
    try:
        document = get_owned_document(
            document_id, user_id=request.user.app_user.id
        )
    except PermissionError:
        return Response({"error": "Document not found."}, status=404)
    except ValueError:
        return Response({"error": "Invalid document reference."}, status=400)

    try:
        current = analysis_is_current(
            document,
            source_hash=source_fingerprint(document),
            model_id=configured_model_id(),
        )
    except RuntimeError:
        current = False

    analysis_status = document.analysis_status
    if analysis_status == "ready" and not current:
        analysis_status = "pending"

    return Response({
        "documentId": str(document.id),
        "filename": document.filename,
        "extractionStatus": document.status,
        "pagesProcessed": document.pages_processed,
        "totalPages": document.total_pages,
        "analysisStatus": analysis_status,
        "analysis": document.analysis if current else None,
        "analysisError": (
            document.analysis_error if analysis_status == "failed" else ""
        ),
    })


@api_view(["POST"])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([QuizRateThrottle])
def document_analyze(request, document_id):
    user_id = request.user.app_user.id
    try:
        claim = claim_document_analysis(document_id, user_id=user_id)
    except PermissionError:
        return Response({"error": "Document not found."}, status=404)
    except ValueError:
        return Response(
            {"error": "Document is not available for analysis."}, status=409
        )
    except RuntimeError:
        return Response(
            {"error": "Document analysis is not configured."}, status=503
        )

    if claim["state"] == "cached":
        return Response({
            "documentId": str(document_id),
            "analysisStatus": "ready",
            "analysis": claim["analysis"],
            "reused": True,
        })
    if claim["state"] == "busy":
        return Response({
            "documentId": str(document_id),
            "analysisStatus": "processing",
        }, status=202)

    try:
        result = analyze_document(claim["document"], user_id=user_id)
        saved = finish_document_analysis(
            document_id,
            user_id=user_id,
            claim_token=claim["claim_token"],
            source_hash=claim["source_hash"],
            model_id=claim["model_id"],
            result=result,
        )
        if not saved:
            return Response({
                "error": "Analysis ownership changed. Reload the document."
            }, status=409)
        return Response({
            "documentId": str(document_id),
            "analysisStatus": "ready",
            "analysis": result,
            "reused": False,
        })
    except Exception as exc:
        import traceback

        locations = " -> ".join(
            f"{frame.name}:{frame.lineno}"
            for frame in traceback.extract_tb(exc.__traceback__)
        )
        logger.warning(
            "Document analysis failed: document_id=%s type=%s locations=%s",
            document_id,
            type(exc).__name__,
            locations,
        )
        fail_document_analysis(
            document_id,
            user_id=user_id,
            claim_token=claim["claim_token"],
        )
        return Response({
            "error": "Document analysis could not be completed.",
            "analysisStatus": "failed",
        }, status=503)


@api_view(["POST"])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([EvaluationRateThrottle])
def document_assess(request, document_id):
    topic_id = request.data.get("topicId")
    answer = request.data.get("answer")
    if (
        not isinstance(topic_id, str) or not topic_id.strip()
        or not isinstance(answer, str) or not answer.strip()
        or len(answer) > 4000
    ):
        return Response(
            {"error": "A concept ID and an answer of 1 to 4000 characters are required."},
            status=400,
        )
    try:
        document = get_owned_document(
            document_id, user_id=request.user.app_user.id
        )
    except PermissionError:
        return Response({"error": "Document not found."}, status=404)

    try:
        if not analysis_is_current(
            document,
            source_hash=source_fingerprint(document),
            model_id=configured_model_id(),
        ):
            return Response({"error": "Current document analysis is required."}, status=409)

        concepts = [
            item for item in document.analysis["concepts"]
            if isinstance(item, dict) and item.get("id") == topic_id.strip()
        ]
        if len(concepts) != 1:
            return Response({"error": "Concept not found."}, status=404)

        concept = concepts[0]
        ids = concept.get("supporting_chunk_ids")
        if (
            not isinstance(ids, list) or not ids
            or any(type(item) is not int for item in ids)
            or len(set(ids)) != len(ids)
        ):
            return Response({"error": "Invalid concept evidence."}, status=409)

        chunks = [
            chunk for chunk in document.chunks
            if isinstance(chunk, dict) and chunk.get("id") in ids
        ]
        if (
            len(chunks) != len(ids)
            or {chunk.get("id") for chunk in chunks} != set(ids)
            or any(
                type(chunk.get("page")) is not int
                or not 1 <= chunk["page"] <= document.total_pages
                for chunk in chunks
            )
        ):
            return Response({"error": "Concept evidence is unavailable."}, status=409)

        feedback = assess_explanation(
            topic=concept["title"],
            answer=answer.strip(),
            chunks=chunks,
        )

        strengths = feedback.get("demonstrated_strengths", [])
        gaps = feedback.get("likely_gaps", [])

        if gaps:
            learning_status = "needs_reinforcement"
        elif strengths:
            learning_status = "developing"
        else:
            learning_status = "new"

        concept_key = f"document:{document.id}:concept:{topic_id.strip()}"

        state, _ = LearnerConceptState.objects.get_or_create(
            user=request.user.app_user,
            concept_key=concept_key,
            defaults={
                "concept_name": concept["title"],
            },
        )

        LearnerConceptState.objects.filter(pk=state.pk).update(
            concept_name=concept["title"],
            status=learning_status,
            strengths=strengths,
            likely_gaps=gaps,
            recommended_next_action=feedback["recommended_next_action"],
            evidence_count=F("evidence_count") + 1,
            last_evidence_at=timezone.now(),
        )

        return Response({"topicId": topic_id.strip(), **feedback})
    except Exception:
        logger.warning("Document feedback failed for document_id=%s", document_id)
        return Response({"error": "Feedback is temporarily unavailable."}, status=503)
