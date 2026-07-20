from django.db import migrations

NEW_MAX_LEVEL = 2


def clamp_levels(apps, schema_editor):
    """Максимальный уровень снижен с 3 до 2 — уровни выше приводим к 2."""
    CardProgress = apps.get_model('courses', 'CardProgress')
    CardProgress.objects.filter(level__gt=NEW_MAX_LEVEL).update(level=NEW_MAX_LEVEL)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0009_enrollment_answers_correct_enrollment_answers_wrong_and_more'),
    ]

    operations = [
        migrations.RunPython(clamp_levels, migrations.RunPython.noop),
    ]
