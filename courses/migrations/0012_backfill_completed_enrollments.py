from django.db import migrations


def backfill(apps, schema_editor):
    """Существующим завершённым записям проставляем историю прохождений:
    курс был пройден хотя бы раз, число прохождений — 1."""
    Enrollment = apps.get_model('courses', 'Enrollment')
    Enrollment.objects.filter(status='completed').update(
        ever_completed=True, completions_count=1,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0011_enrollment_completions_count_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
