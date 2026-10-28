import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0025_leader_inquiries'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PopulationFigure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.IntegerField(db_index=True)),
                ('level', models.CharField(choices=[('country', 'Country'), ('province', 'Province'), ('district', 'District'), ('sector', 'Sector'), ('cell', 'Cell'), ('village', 'Village')], max_length=10)),
                ('year', models.IntegerField()),
                ('kind', models.CharField(choices=[('census', 'Census'), ('projection', 'Projection'), ('manual', 'Local count')], default='census', max_length=10)),
                ('total', models.IntegerField()),
                ('male', models.IntegerField(blank=True, null=True)),
                ('female', models.IntegerField(blank=True, null=True)),
                ('urban', models.IntegerField(blank=True, null=True)),
                ('rural', models.IntegerField(blank=True, null=True)),
                ('households', models.IntegerField(blank=True, null=True)),
                ('source', models.CharField(blank=True, default='', max_length=200)),
                ('note', models.TextField(blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='population_figures', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['location', 'year'],
                'unique_together': {('location', 'year', 'kind')},
            },
        ),
        migrations.CreateModel(
            name='CensusIndicator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.IntegerField(db_index=True)),
                ('level', models.CharField(choices=[('country', 'Country'), ('province', 'Province'), ('district', 'District'), ('sector', 'Sector'), ('cell', 'Cell'), ('village', 'Village')], max_length=10)),
                ('year', models.IntegerField()),
                ('key', models.CharField(db_index=True, max_length=50)),
                ('value', models.FloatField()),
                ('source', models.CharField(blank=True, default='', max_length=200)),
            ],
            options={
                'ordering': ['location', 'year', 'key'],
                'unique_together': {('location', 'year', 'key')},
            },
        ),
    ]
