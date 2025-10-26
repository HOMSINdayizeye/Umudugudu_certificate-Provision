import csv
from django.core.management.base import BaseCommand
from certificates.models import EligiblePerson

class Command(BaseCommand):
    help = 'Load eligible people from a CSV file. CSV headers: first_name,last_name,email,national_id'

    def add_arguments(self, parser):
        parser.add_argument('csvfile', type=str)

    def handle(self, *args, **options):
        path = options['csvfile']
        count = 0
        with open(path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email = row.get('email')
                if not email:
                    continue
                obj, created = EligiblePerson.objects.update_or_create(
                    email=email.strip().lower(),
                    defaults={
                        'first_name': row.get('first_name','').strip(),
                        'last_name': row.get('last_name','').strip(),
                        'national_id': row.get('national_id','').strip() if row.get('national_id') else None,
                    }
                )
                if created:
                    count += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded/updated eligibles from {path}. New entries: {count}'))