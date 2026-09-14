from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("tutoring", "0002_seed_subjects"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("filename", models.CharField(max_length=255)),
                ("stored_path", models.CharField(max_length=500)),
                ("status", models.CharField(choices=[("ready", "ready"), ("partial", "partial"), ("failed", "failed")], max_length=10)),
                ("overview", models.TextField(blank=True)),
                ("topics", models.JSONField(default=list)),
                ("chunks", models.JSONField(default=list)),
                ("pages_processed", models.PositiveIntegerField(default=0)),
                ("total_pages", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="study_documents", to="accounts.appuser")),
            ],
        ),
    ]