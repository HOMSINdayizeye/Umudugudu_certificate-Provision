import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mark_existing_accepted(apps, schema_editor):
    # Transfers recorded before this migration were applied immediately, so they count as accepted
    CitizenTransfer = apps.get_model('certificates', 'CitizenTransfer')
    CitizenTransfer.objects.all().update(status='accepted')


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0020_death_reports'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='citizentransfer',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='pending', max_length=10),
        ),
        migrations.AddField(
            model_name='citizentransfer',
            name='decided_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='citizen_transfer_decisions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='citizentransfer',
            name='decided_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='citizentransfer',
            name='decision_note',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(mark_existing_accepted, migrations.RunPython.noop),
    ]
