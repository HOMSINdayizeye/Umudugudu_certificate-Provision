from django.db import migrations


def forwards(apps, schema_editor):
    ServicePayment = apps.get_model('certificates', 'ServicePayment')
    Citizen = apps.get_model('certificates', 'Citizen')
    for payment in ServicePayment.objects.select_related('citizen'):
        user = payment.citizen
        record, _ = Citizen.objects.get_or_create(
            national_id=f'user-{user.pk}',
            defaults={
                'first_name': user.first_name or user.username,
                'last_name': user.last_name or '',
                'email': user.email or '',
                'phone': '',
                'age': 0,
                'village': user.village or 0,
                'isibo': user.isibo or '',
            },
        )
        payment.citizen_record = record
        payment.save(update_fields=['citizen_record'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('certificates', '0006_alter_servicepayment_unique_together_citizen_and_more'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
