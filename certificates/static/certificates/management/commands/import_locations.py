import csv
from django.core.management.base import BaseCommand
from certificates.models import Location

class Command(BaseCommand):
    help = 'Import location data from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        created = 0
        skipped = 0

        try:
            with open(csv_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Adjust this mapping to match your actual CSV structure
                    Location.objects.create(
                        province=row.get('province', ''),
                        district=row.get('district', ''),
                        sector=row.get('sector', ''),
                        cell=row.get('cell', ''),
                        village=row.get('village', ''),
                        code=int(row.get('code', 0))
                    )
                    created += 1

            self.stdout.write(self.style.SUCCESS(
                f"Import complete: {created} locations added"
            ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error importing CSV: {e}"))
