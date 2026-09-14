import uuid

from django.db import models

from accounts.models import AppUser

TEACHING_MODES = [
    ("beginner", "Beginner"),
    ("standard", "Standard"),
    ("deep", "Deep"),
    ("socratic", "Socratic"),
    ("practice", "Practice"),
]


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class Topic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="topics")
    slug = models.SlugField()
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ("subject", "slug")

    def __str__(self) -> str:
        return f"{self.subject.name} / {self.name}"


class StudyDocument(models.Model):
    STATUS_CHOICES = [
        ("ready", "ready"),
        ("partial", "partial"),
        ("failed", "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="study_documents")
    filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    overview = models.TextField(blank=True)
    topics = models.JSONField(default=list)
    chunks = models.JSONField(default=list)
    pages_processed = models.PositiveIntegerField(default=0)
    total_pages = models.PositiveIntegerField(default=0)

    analysis_status = models.CharField(
        max_length=10,
        choices=[
            ("pending", "pending"),
            ("processing", "processing"),
            ("ready", "ready"),
            ("failed", "failed"),
        ],
        default="pending",
    )
    analysis = models.JSONField(default=dict, blank=True)
    analysis_version = models.CharField(max_length=100, blank=True)
    analysis_source_hash = models.CharField(max_length=64, blank=True)
    analysis_model_id = models.CharField(max_length=255, blank=True)
    analysis_error = models.CharField(max_length=500, blank=True)
    analysis_started_at = models.DateTimeField(null=True, blank=True)
    analysis_completed_at = models.DateTimeField(null=True, blank=True)
    analysis_claim_token = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class LearningSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="learning_sessions")
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    mode = models.CharField(max_length=20, choices=TEACHING_MODES, default="standard")
    created_at = models.DateTimeField(auto_now_add=True)


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="conversations")
    learning_session = models.ForeignKey(
        LearningSession, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    ROLE_CHOICES = [("user", "user"), ("assistant", "assistant"), ("system", "system")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AgentRun(models.Model):
    """Minimal observability stub (Part XXVI), populated from Agents SDK run results."""

    STATUS_CHOICES = [("success", "success"), ("error", "error")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="agent_runs")
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True, on_delete=models.SET_NULL
    )
    agent_name = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    latency_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EvaluationToken(models.Model):
    KIND_CHOICES = [("objective", "objective"), ("theory", "theory")]
    STATUS_CHOICES = [
        ("issued", "issued"),
        ("processing", "processing"),
        ("consumed", "consumed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="evaluation_tokens")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    grading_payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="issued")
    claim_token = models.UUIDField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["expires_at"]),
        ]


class LearningEvidence(models.Model):
    QUESTION_TYPE_CHOICES = [("objective", "objective"), ("theory", "theory")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="learning_evidence",
    )
    evaluation_token = models.OneToOneField(
        EvaluationToken,
        on_delete=models.PROTECT,
        related_name="learning_evidence",
    )
    topic = models.CharField(max_length=200)
    question = models.TextField(max_length=2000)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES)
    submitted_answer = models.TextField(max_length=6000)
    score = models.PositiveSmallIntegerField()
    feedback = models.TextField(max_length=12000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__gte=0, score__lte=100),
                name="learning_evidence_score_0_100",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "topic", "created_at"]),
        ]


class LearnerConceptState(models.Model):
    STATUS_CHOICES = [
        ("new", "new"),
        ("developing", "developing"),
        ("proficient", "proficient"),
        ("needs_reinforcement", "needs_reinforcement"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name="concept_states",
    )

    concept_key = models.CharField(max_length=255)
    concept_name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
    )

    strengths = models.JSONField(default=list, blank=True)
    likely_gaps = models.JSONField(default=list, blank=True)
    recommended_next_action = models.TextField(blank=True)

    evidence_count = models.PositiveIntegerField(default=0)
    last_evidence_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "concept_key"],
                name="unique_user_concept_state",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} / {self.concept_name} / {self.status}"