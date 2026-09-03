from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('certificates', '0007_migrate_payments_to_citizen_records'),
    ]
    operations = [
        migrations.RemoveField(model_name='servicepayment', name='citizen'),
        migrations.RenameField(model_name='servicepayment', old_name='citizen_record', new_name='citizen'),
        migrations.AlterField(
            model_name='servicepayment',
            name='citizen',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='payments', to='certificates.citizen'),
        ),
        migrations.AlterUniqueTogether(
            name='servicepayment',
            unique_together={('citizen', 'service', 'trimester', 'year')},
        ),
    ]
