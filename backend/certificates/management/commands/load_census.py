"""Load the NISR census CSVs (certificates/data/nisr) into PopulationFigure and CensusIndicator.

    python manage.py load_census            # load or refresh everything
    python manage.py load_census --dir X    # CSVs from another folder (same file names)

Area names in the CSVs are matched to LocationImport: districts by name, sectors by name inside their district
(with a fuzzy fallback for spelling differences such as Mageregere / Mageragere). Unmatched rows are listed at
the end so they can be fixed by hand. Rows are written in bulk (upsert), so running the command again updates
them in place and stays fast on a remote database.
"""
import csv
import difflib
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import TextField
from django.db.models.functions import Cast

from certificates.models import LocationImport, PopulationFigure, CensusIndicator
from certificates import census

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'nisr')
BATCH = 1000

# Province names as the workbooks write them -> as the location import names them (Kinyarwanda or English)
PROVINCE_NAMES = {
    'City of Kigali': ['umujyi wa kigali', 'kigali city', 'city of kigali', 'kigali'],
    'Southern Province': ['amajyepfo', 'southern province', 'south'],
    'Western Province': ['iburengerazuba', 'western province', 'west'],
    'Northern Province': ['amajyaruguru', 'northern province', 'north'],
    'Eastern Province': ['iburasirazuba', 'eastern province', 'east'],
}


def norm(s):
    return ' '.join((s or '').lower().replace('-', ' ').split())


def num(v, as_int=False):
    if v in (None, ''):
        return None
    f = float(v)
    return int(round(f)) if as_int else f


class Command(BaseCommand):
    help = 'Load the NISR 2022 census and 2023-2032 projection datasets into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default=DATA_DIR, help='Folder holding the CSV files')

    def handle(self, *args, **options):
        folder = options['dir']
        self.unmatched = []
        self.figures = {}      # (location, year, kind) -> field dict
        self.indicators = {}   # (location, year, key) -> field dict
        self.districts = {norm(r.name): r.location_id for r in LocationImport.objects.filter(type='DISTRICT')}
        self.provinces = {}
        provinces = list(LocationImport.objects.filter(type='PROVINCE'))
        for canonical, spellings in PROVINCE_NAMES.items():
            match = next((p for p in provinces if norm(p.name) in spellings), None)
            if match:
                self.provinces[canonical] = match.location_id
        self._sectors = {}

        self.load_sector_population(os.path.join(folder, 'sector_population_2022.csv'))
        self.load_sector_indicators(os.path.join(folder, 'sector_indicators_2022.csv'))
        self.load_area_population(os.path.join(folder, 'area_population_2022.csv'))
        self.load_area_indicators(os.path.join(folder, 'area_indicators_2022.csv'))
        self.load_projections(os.path.join(folder, 'district_projections_2023_2032.csv'))
        self.load_national_projections(os.path.join(folder, 'national_projections_2022_2052.csv'))
        self.load_age_groups(os.path.join(folder, 'national_age_groups_2022.csv'))

        # The households count also belongs on the sector's population figure
        for (location, year, key), row in self.indicators.items():
            if key == 'households' and (location, year, 'census') in self.figures:
                self.figures[(location, year, 'census')]['households'] = int(row['value'])

        with transaction.atomic():
            self.flush()
        census.clear_cache()

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {len(self.figures)} population figures and {len(self.indicators)} indicators.'))
        if self.unmatched:
            self.stdout.write(self.style.WARNING(f'{len(self.unmatched)} rows could not be matched to a location:'))
            for row in sorted(set(self.unmatched)):
                self.stdout.write(f'  - {row}')

    # --- matching ---
    def district_id(self, name):
        return self.districts.get(norm(name))

    def province_id(self, name):
        return self.provinces.get(name) or self.provinces.get(
            next((c for c, s in PROVINCE_NAMES.items() if norm(name) in s), None))

    def area_id(self, level, name):
        if level == 'country':
            return 0
        if level == 'province':
            return self.province_id(name)
        if level == 'district':
            return self.district_id(name)
        return None

    def sectors_of(self, district_id):
        if district_id not in self._sectors:
            qs = LocationImport.objects.filter(type='SECTOR').annotate(_s=Cast('location_id', TextField()))
            qs = qs.filter(_s__startswith=str(district_id))
            self._sectors[district_id] = {norm(r.name): r.location_id for r in qs}
        return self._sectors[district_id]

    def sector_id(self, district_name, sector_name):
        district = self.district_id(district_name)
        if not district:
            self.unmatched.append(f'district "{district_name}"')
            return None
        sectors = self.sectors_of(district)
        key = norm(sector_name)
        if key in sectors:
            return sectors[key]
        close = difflib.get_close_matches(key, list(sectors), n=1, cutoff=0.75)
        if close:
            return sectors[close[0]]
        self.unmatched.append(f'sector "{sector_name}" in {district_name}')
        return None

    # --- collectors ---
    def put_figure(self, location, level, year, kind, source, **values):
        self.figures[(location, year, kind)] = {'level': level, 'source': source, **values}

    def put_indicator(self, location, level, year, key, value, source):
        if value is not None:
            self.indicators[(location, year, key)] = {'level': level, 'value': float(value), 'source': source}

    def flush(self):
        figure_fields = ['level', 'source', 'total', 'male', 'female', 'urban', 'rural', 'households', 'updated_at']
        objs = [PopulationFigure(location=loc, year=year, kind=kind, **vals) for (loc, year, kind), vals in self.figures.items()]
        for i in range(0, len(objs), BATCH):
            PopulationFigure.objects.bulk_create(objs[i:i + BATCH], update_conflicts=True,
                                                 unique_fields=['location', 'year', 'kind'], update_fields=figure_fields)
        objs = [CensusIndicator(location=loc, year=year, key=key, **vals) for (loc, year, key), vals in self.indicators.items()]
        for i in range(0, len(objs), BATCH):
            CensusIndicator.objects.bulk_create(objs[i:i + BATCH], update_conflicts=True,
                                                unique_fields=['location', 'year', 'key'],
                                                update_fields=['level', 'value', 'source'])

    def rows(self, path):
        if not os.path.exists(path):
            self.stdout.write(self.style.WARNING(f'missing {path}'))
            return []
        with open(path, newline='', encoding='utf-8') as fh:
            return list(csv.DictReader(fh))

    # --- loaders ---
    def load_sector_population(self, path):
        for r in self.rows(path):
            loc = self.sector_id(r['district'], r['sector'])
            if loc:
                self.put_figure(loc, 'sector', census.CENSUS_YEAR, 'census', census.SOURCE_CENSUS,
                                total=num(r['total'], True), male=num(r['male'], True), female=num(r['female'], True),
                                urban=num(r['urban'], True), rural=num(r['rural'], True))

    def load_sector_indicators(self, path):
        for r in self.rows(path):
            loc = self.sector_id(r['district'], r['sector'])
            if loc:
                self.put_indicator(loc, 'sector', census.CENSUS_YEAR, r['key'], num(r['value']), census.SOURCE_CENSUS)

    def load_area_population(self, path):
        for r in self.rows(path):
            loc = self.area_id(r['level'], r['name'])
            if loc is None:
                self.unmatched.append(f"{r['level']} \"{r['name']}\"")
                continue
            self.put_figure(loc, r['level'], census.CENSUS_YEAR, 'census', census.SOURCE_CENSUS,
                            total=num(r['total'], True), male=num(r['male'], True), female=num(r['female'], True),
                            urban=num(r['urban'], True), rural=num(r['rural'], True))
            for key in ('children_0_17', 'youth_16_30', 'women', 'elderly_60plus', 'disabled_5plus', 'density'):
                self.put_indicator(loc, r['level'], census.CENSUS_YEAR, key, num(r.get(key)), census.SOURCE_CENSUS)

    def load_area_indicators(self, path):
        for r in self.rows(path):
            loc = self.area_id(r['level'], r['name'])
            if loc is None:
                self.unmatched.append(f"{r['level']} \"{r['name']}\"")
                continue
            self.put_indicator(loc, r['level'], census.CENSUS_YEAR, r['key'], num(r['value']), census.SOURCE_CENSUS)

    def load_projections(self, path):
        bands = ('children_0_17', 'youth_16_30', 'working_16_64', 'elderly_60plus', 'school_6_17', 'under_5')
        for r in self.rows(path):
            loc = self.district_id(r['district'])
            if not loc:
                self.unmatched.append(f"district \"{r['district']}\"")
                continue
            year = int(r['year'])
            self.put_figure(loc, 'district', year, 'projection', census.SOURCE_PROJECTION,
                            total=num(r['total'], True), male=num(r['male'], True), female=num(r['female'], True))
            for key in bands:
                self.put_indicator(loc, 'district', year, key, num(r.get(key)), census.SOURCE_PROJECTION)

    def load_national_projections(self, path):
        for r in self.rows(path):
            year = int(r['year'])
            if year == census.CENSUS_YEAR:
                continue   # the census count itself is loaded from the main indicators
            self.put_figure(0, 'country', year, 'projection', census.SOURCE_NATIONAL_PROJECTION,
                            total=num(r['medium'], True))
            self.put_indicator(0, 'country', year, 'projection_high', num(r['high']), census.SOURCE_NATIONAL_PROJECTION)
            self.put_indicator(0, 'country', year, 'projection_low', num(r['low']), census.SOURCE_NATIONAL_PROJECTION)

    def load_age_groups(self, path):
        for r in self.rows(path):
            if r['age_group'].lower() == 'total':
                continue
            self.put_indicator(0, 'country', census.CENSUS_YEAR, f"age_{r['age_group'].replace('-', '_')}",
                               num(r['total']), census.SOURCE_CENSUS)
