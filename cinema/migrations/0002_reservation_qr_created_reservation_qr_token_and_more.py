"""Safer migration: add nullable qr_token, populate unique tokens, then enforce unique/not-null.

Generated manually to avoid UNIQUE constraint failures on SQLite when adding a unique UUID
field to an existing table.
"""

from uuid import uuid4
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion


def populate_qr_tokens(apps, schema_editor):
    Reservation = apps.get_model('cinema', 'Reservation')
    for r in Reservation.objects.all():
        if not r.qr_token:
            r.qr_token = uuid4()
            r.save()


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('cinema', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='qr_created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # Add token as nullable first to avoid unique constraint issues on SQLite
        migrations.AddField(
            model_name='reservation',
            name='qr_token',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name='reservation',
            name='qr_used_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='qr_used_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='used_qr_reservations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='reservation',
            name='qr_valid',
            field=models.BooleanField(default=True),
        ),
        # Populate unique tokens for existing rows
        migrations.RunPython(populate_qr_tokens, reverse_code=noop),
        # Enforce uniqueness and not-null after population
        migrations.AlterField(
            model_name='reservation',
            name='qr_token',
            field=models.UUIDField(editable=False, unique=True),
        ),
    ]
