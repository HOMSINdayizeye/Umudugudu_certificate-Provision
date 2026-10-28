"""Census estimates and coverage: derived cell/village figures, projection growth, local counts, API scope."""
from django.test import TestCase
from rest_framework.test import APIClient

from . import census
from .models import Citizen, CustomUser, LocationImport, PopulationFigure, CensusIndicator

# District 11 > sector 1101 > cells 110101 (2 villages) and 110102 (1 village); sector 1102 (no census row)
DISTRICT, SECTOR, CELL_A, CELL_B = 11, 1101, 110101, 110102
V1, V2, V3 = 11010101, 11010102, 11010201


def make_locations():
    rows = [(0, 'COUNTRY', 'Rwanda'), (1, 'PROVINCE', 'Umujyi wa Kigali'), (DISTRICT, 'DISTRICT', 'Nyarugenge'),
            (SECTOR, 'SECTOR', 'Gitega'), (1102, 'SECTOR', 'Kanyinya'), (CELL_A, 'CELL', 'Akabahizi'),
            (CELL_B, 'CELL', 'Akabeza'), (V1, 'VILLAGE', 'Gihanga'), (V2, 'VILLAGE', 'Iterambere'),
            (V3, 'VILLAGE', 'Izuba'), (11020101, 'VILLAGE', 'Elsewhere')]
    for loc, kind, name in rows:
        LocationImport.objects.create(location_id=loc, type=kind, name=name, status='ACTIVE')


def make_census():
    PopulationFigure.objects.create(location=DISTRICT, level='district', year=2022, kind='census', total=100000,
                                    male=50000, female=50000)
    PopulationFigure.objects.create(location=DISTRICT, level='district', year=2024, kind='projection', total=110000)
    PopulationFigure.objects.create(location=SECTOR, level='sector', year=2022, kind='census', total=3000, male=1500,
                                    female=1500, households=600)
    CensusIndicator.objects.create(location=SECTOR, level='sector', year=2022, key='households', value=600)
    CensusIndicator.objects.create(location=DISTRICT, level='district', year=2022, key='hh_electricity_pct', value=61)


def citizen(village, n):
    return Citizen.objects.create(first_name=f'C{n}', last_name='X', national_id=f'1{n:015d}', age=30, village=village)


class EstimatorTests(TestCase):
    def setUp(self):
        make_locations()
        make_census()

    def test_village_and_cell_share_the_sector_census(self):
        e = census.Estimator(year=2022)
        village = e.estimate(V1)
        # 3 villages in the sector: each gets 1000 people and 200 households
        self.assertEqual((village['census'], village['estimate'], village['households'], village['method']),
                         (1000, 1000, 200, 'derived'))
        cell = e.estimate(CELL_A)
        self.assertEqual((cell['census'], cell['estimate'], cell['share']), (2000, 2000, round(2 / 3, 5)))
        self.assertEqual(e.estimate(SECTOR)['method'], 'census')

    def test_estimate_grows_with_the_district_projection(self):
        e = census.Estimator(year=2024)
        self.assertEqual(e.estimate(V1)['estimate'], 1100)          # ×1.1
        self.assertEqual(e.estimate(SECTOR)['estimate'], 3300)
        # Years beyond the published projections use the last projected year; before 2022 the census itself
        self.assertEqual(census.Estimator(year=2040).estimate(SECTOR)['estimate'], 3300)
        self.assertEqual(census.Estimator(year=2020).estimate(SECTOR)['estimate'], 3000)

    def test_local_count_replaces_the_derived_estimate(self):
        PopulationFigure.objects.create(location=V1, level='village', year=2024, kind='manual', total=1500, note='headcount')
        est = census.Estimator(year=2024).estimate(V1)
        self.assertEqual((est['method'], est['estimate'], est['local_count']['total']), ('local', 1500, 1500))
        # A 2024 count is not grown again for 2024 but the derived census share is still reported
        self.assertEqual(est['census'], 1000)

    def test_sector_without_census_row_gives_no_estimate(self):
        est = census.Estimator().estimate(11020101)
        self.assertIsNone(est['estimate'])

    def test_coverage_counts_living_citizens_by_prefix(self):
        for n in range(3):
            citizen(V1, n)
        citizen(V3, 9)
        dead = citizen(V1, 10)
        dead.status = 'deceased'
        dead.save()
        cov = census.Estimator(year=2022).coverage(V1)
        by_level = {r['level']: r for r in cov['chain']}
        self.assertEqual([r['level'] for r in cov['chain']], ['village', 'cell', 'sector', 'district'])
        self.assertEqual((by_level['village']['registered'], by_level['cell']['registered'],
                          by_level['sector']['registered'], by_level['district']['registered']), (3, 3, 4, 4))
        self.assertEqual(by_level['village']['coverage_pct'], 0.3)
        self.assertEqual(by_level['village']['gap'], 997)
        # A cell lists its villages as children; a village has none
        self.assertEqual(cov['children'], [])
        cell_cov = census.Estimator(year=2022).coverage(CELL_A)
        self.assertEqual([c['name'] for c in cell_cov['children']], ['Gihanga', 'Iterambere'])


class CensusApiTests(TestCase):
    def setUp(self):
        make_locations()
        make_census()
        self.village_leader = CustomUser.objects.create_user(username='vl', password='x', role='village_leader',
                                                             village=V1, cell=CELL_A, sector=SECTOR, district=DISTRICT)
        self.other_leader = CustomUser.objects.create_user(username='vl2', password='x', role='village_leader',
                                                           village=11020101, cell=110201, sector=1102, district=DISTRICT)
        self.isibo = CustomUser.objects.create_user(username='isibo', password='x', role='isibo_leader', village=V1)
        self.admin = CustomUser.objects.create_superuser(username='admin', password='x')

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_coverage_defaults_to_own_area_and_refuses_unrelated_areas(self):
        c = self.client_for(self.village_leader)
        res = c.get('/api/census/coverage/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['name'], 'Gihanga')
        self.assertTrue(res.data['can_manage'])
        # Areas above the leader's own are fine, a village in another sector is not
        self.assertEqual(c.get('/api/census/coverage/', {'location': SECTOR}).status_code, 200)
        self.assertEqual(c.get('/api/census/coverage/', {'location': 11020101}).status_code, 403)
        self.assertEqual(c.get('/api/census/coverage/', {'location': 99999999}).status_code, 404)
        # Admins see everything, isibo leaders cannot enter counts
        self.assertEqual(self.client_for(self.admin).get('/api/census/coverage/', {'location': 11020101}).status_code, 200)
        self.assertFalse(self.client_for(self.isibo).get('/api/census/coverage/').data['can_manage'])

    def test_area_returns_indicators_and_projections(self):
        res = self.client_for(self.isibo).get('/api/census/area/', {'location': V1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual([a['level'] for a in res.data['areas']], ['sector', 'district', 'province', 'country'])
        district = res.data['areas'][1]
        self.assertEqual(district['indicators'][0]['label'], 'Households lit by electricity')
        self.assertEqual(res.data['projections'][0]['year'], 2024)
        self.assertEqual(res.data['estimate']['method'], 'derived')

    def test_local_count_is_scoped_to_cells_and_villages_inside_the_leaders_area(self):
        c = self.client_for(self.village_leader)
        res = c.put('/api/census/local-count/', {'location': V1, 'total': 1200, 'households': 250, 'year': 2025,
                                                 'note': 'headcount'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['coverage']['method'], 'local')
        self.assertEqual(PopulationFigure.objects.get(location=V1, kind='manual').updated_by, self.village_leader)
        # Not a sector, not another leader's village, not negative
        self.assertEqual(c.put('/api/census/local-count/', {'location': SECTOR, 'total': 5}, format='json').status_code, 400)
        self.assertEqual(c.put('/api/census/local-count/', {'location': V2, 'total': 5}, format='json').status_code, 403)
        self.assertEqual(c.put('/api/census/local-count/', {'location': V1, 'total': -5}, format='json').status_code, 400)
        self.assertEqual(self.client_for(self.isibo).put('/api/census/local-count/', {'location': V1, 'total': 5},
                                                         format='json').status_code, 403)
        res = c.delete(f'/api/census/local-count/?location={V1}')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(PopulationFigure.objects.filter(location=V1, kind='manual').exists())
        self.assertEqual(res.data['coverage']['method'], 'derived')

    def test_datasets_summary(self):
        res = self.client_for(self.village_leader).get('/api/census/datasets/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(sum(d['rows'] for d in res.data['datasets']), 5)
        self.assertIn('hh_electricity_pct', [i['key'] for i in res.data['indicators']])
