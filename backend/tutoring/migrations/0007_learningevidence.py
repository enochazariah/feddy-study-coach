from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("tutoring", "0006_evaluationtoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningEvidence",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("topic", models.CharField(max_length=200)),
                ("question", models.TextField(max_length=2000)),
                (
                    "question_type",
                    models.CharField(
                        choices=[("objective", "objective"), ("theory", "theory")],
                        max_length=10,
                    ),
                ),
                ("submitted_answer", models.TextField(max_length=6000)),
                ("score", models.PositiveSmallIntegerField()),
                ("feedback", models.TextField(max_length=12000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "evaluation_token",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="learning_evidence",
                        to="tutoring.evaluationtoken",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="learning_evidence",
                        to="accounts.appuser",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(score__gte=0, score__lte=100),
                        name="learning_evidence_score_0_100",
                    ),
                ],
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="tutoring_le_user_id_cfa13f_idx"),
                    models.Index(fields=["user", "topic", "created_at"], name="tutoring_le_user_id_4a8a2c_idx"),
                ],
            },
        ),
    ]