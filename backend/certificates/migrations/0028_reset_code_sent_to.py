from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0027_password_reset_code'),
    ]

    operations = [
        # The code now goes to an email address (up to 254 characters) or a phone number
        migrations.RenameField(model_name='passwordresetcode', old_name='phone', new_name='sent_to'),
        migrations.AlterField(model_name='passwordresetcode', name='sent_to', field=models.CharField(max_length=254)),
    ]
