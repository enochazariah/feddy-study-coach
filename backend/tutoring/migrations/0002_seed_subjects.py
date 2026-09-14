import uuid

from django.db import migrations


def seed_subjects(apps, schema_editor):
    Subject = apps.get_model("tutoring", "Subject")
    for slug, name in [("machine-learning", "Machine Learning"), ("mathematics", "Mathematics")]:
        Subject.objects.get_or_create(slug=slug, defaults={"id": uuid.uuid4(), "name": name})


def unseed_subjects(apps, schema_editor):
    Subject = apps.get_model("tutoring", "Subject")
    Subject.objects.filter(slug__in=["machine-learning", "mathematics"]).delete()


class Migration(migrations.Migration):
    dependencies = [("tutoring", "0001_initial")]
    operations = [migrations.RunPython(seed_subjects, unseed_subjects)]
