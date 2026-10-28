"""Census population estimates and registration coverage.

NISR publishes the 2022 census down to sector level and yearly projections (2023-2032) per district. Cells and
villages have no published figure, so their estimate is the sector's census population shared out by the number of
villages (every village gets an equal share, a cell gets the share of its villages). A leader may replace that with a
local count (PopulationFigure kind='manual'), which then takes precedence. Every estimate is grown to the requested
year with the district's projection, so "estimated now" follows NISR's growth path.

The database is remote (every query is a network round trip), so the Estimator loads everything an area needs in a
few bulk queries (`preload`) and the static NISR lookups are cached for a few minutes.
"""
from django.core.cache import cache
from django.db.models import TextField, Count, Min, Max
from django.db.models.functions import Cast
from django.utils import timezone

from .models import LocationImport, PopulationFigure, CensusIndicator, Citizen

CENSUS_YEAR = 2022
PROJECTION_YEARS = (2023, 2032)
LEVELS = ['country', 'province', 'district', 'sector', 'cell', 'village']
LEVEL_DIGITS = {'country': 0, 'province': 1, 'district': 2, 'sector': 4, 'cell': 6, 'village': 8}
TYPE_OF_LEVEL = {'country': 'COUNTRY', 'province': 'PROVINCE', 'district': 'DISTRICT', 'sector': 'SECTOR',
                 'cell': 'CELL', 'village': 'VILLAGE'}
CHILD_LEVEL = {'country': 'province', 'province': 'district', 'district': 'sector', 'sector': 'cell', 'cell': 'village'}
CACHE_SECONDS = 10 * 60   # NISR figures only change when load_census runs

SOURCE_CENSUS = 'NISR, Fifth Rwanda Population and Housing Census (RPHC5), 2022'
SOURCE_PROJECTION = 'NISR, RPHC5 Subnational Population Projections 2023-2032'
SOURCE_NATIONAL_PROJECTION = 'NISR, RPHC5 Thematic Report: Population Projection 2022-2052 (medium scenario)'

# key -> (label, unit, group); unit: count | percent | index | years
INDICATORS = {
    'children_0_17': ('Children (0-17 years)', 'count', 'Population'),
    'children_share_pct': ('Children share of population', 'percent', 'Population'),
    'youth_16_30': ('Youth (16-30 years)', 'count', 'Population'),
    'youth_share_pct': ('Youth share of population', 'percent', 'Population'),
    'working_16_64': ('Working age (16-64 years)', 'count', 'Population'),
    'school_6_17': ('School age (6-17 years)', 'count', 'Population'),
    'under_5': ('Under 5 years', 'count', 'Population'),
    'elderly_60plus': ('Elderly (60 years and above)', 'count', 'Population'),
    'elderly_share_pct': ('Elderly share of population', 'percent', 'Population'),
    'women': ('Women', 'count', 'Population'),
    'women_share_pct': ('Women share of population', 'percent', 'Population'),
    'pop_5plus': ('Population aged 5 and above', 'count', 'Population'),
    'pop_12plus': ('Population aged 12 and above', 'count', 'Population'),
    'urban_share_pct': ('Living in urban areas', 'percent', 'Population'),
    'mean_age': ('Mean age', 'years', 'Population'),
    'median_age': ('Median age', 'years', 'Population'),
    'density': ('Population density (per km²)', 'index', 'Population'),
    'net_lifetime_migration': ('Net lifetime migration (in minus out)', 'count', 'Population'),
    'net_recent_migration': ('Net recent migration (in minus out)', 'count', 'Population'),
    'disabled_5plus': ('Persons with a disability (5+)', 'count', 'Health & disability'),
    'disability_prevalence_pct': ('Disability prevalence (5+)', 'percent', 'Health & disability'),
    'medical_insurance_pct': ('Covered by medical insurance', 'percent', 'Health & disability'),
    'birth_registration_pct': ('Children with a registered birth', 'percent', 'Health & disability'),
    'households': ('Private households', 'count', 'Households'),
    'female_headship_pct': ('Female household headship rate', 'percent', 'Households'),
    'hh_umudugudu_pct': ('Households in planned settlements (umudugudu)', 'percent', 'Households'),
    'hh_modern_planned_pct': ('Households in modern planned urban housing', 'percent', 'Households'),
    'hh_spontaneous_pct': ('Households in spontaneous / squatter housing', 'percent', 'Households'),
    'hh_improved_water_pct': ('Households with an improved drinking-water source', 'percent', 'Households'),
    'hh_electricity_pct': ('Households lit by electricity', 'percent', 'Households'),
    'hh_radio_pct': ('Households owning a radio', 'percent', 'Households'),
    'hh_tv_pct': ('Households owning a television', 'percent', 'Households'),
    'hh_mobile_pct': ('Households owning a mobile phone', 'percent', 'Households'),
    'hh_smartphone_pct': ('Households owning a smartphone', 'percent', 'Households'),
    'hh_computer_pct': ('Households owning a computer', 'percent', 'Households'),
    'hh_bicycle_pct': ('Households owning a bicycle', 'percent', 'Households'),
    'hh_motorcycle_pct': ('Households owning a motorcycle', 'percent', 'Households'),
    'hh_vehicle_pct': ('Households owning a vehicle', 'percent', 'Households'),
    'internet_10plus_pct': ('Used the internet (10+)', 'percent', 'Digital access'),
    'internet_16plus_pct': ('Used the internet (16+)', 'percent', 'Digital access'),
    'edu_no_primary_pct': ('No primary schooling (12+)', 'percent', 'Education'),
    'edu_secondary_plus_pct': ('Reached secondary or higher (12+)', 'percent', 'Education'),
    'edu_tertiary_pct': ('Reached tertiary education (12+)', 'percent', 'Education'),
    'poverty_nonpoor_pct': ('Non-poor', 'percent', 'Poverty'),
    'poverty_vulnerable_pct': ('Vulnerable to poverty', 'percent', 'Poverty'),
    'poverty_moderate_pct': ('Moderately poor', 'percent', 'Poverty'),
    'poverty_severe_pct': ('Severely poor', 'percent', 'Poverty'),
    'mpi_headcount_pct': ('Multidimensionally poor (MPI headcount)', 'percent', 'Poverty'),
    'mpi_index': ('Multidimensional Poverty Index', 'index', 'Poverty'),
    'projection_high': ('Projected population, high scenario', 'count', 'Projections'),
    'projection_low': ('Projected population, low scenario', 'count', 'Projections'),
}


def level_of(location_id):
    """Administrative level implied by a location id (1 digit province … 8 digit village); None for foreign ids."""
    if location_id is None or int(location_id) < 0:
        return None
    if int(location_id) == 0:
        return 'country'
    n = len(str(int(location_id)))
    for level, digits in LEVEL_DIGITS.items():
        if digits == n:
            return level
    return None


def chain_of(location_id):
    """{level: id} for the location and every area above it, e.g. village 11010101 -> province 1 … village 11010101."""
    s = str(int(location_id))
    out = {'country': 0}
    for level, digits in LEVEL_DIGITS.items():
        if 0 < digits <= len(s):
            out[level] = int(s[:digits])
    return out


def prefix_of(location_id):
    return '' if int(location_id) == 0 else str(int(location_id))


def area_name(location_id):
    row = LocationImport.objects.filter(location_id=location_id).only('name').first()
    return row.name if row else f'Area {location_id}'


def registered_count(location_id):
    """Living registry citizens whose village lies inside the area."""
    qs = Citizen.objects.filter(status='alive')
    prefix = prefix_of(location_id)
    if prefix:
        qs = qs.annotate(_v=Cast('village', TextField())).filter(_v__startswith=prefix)
    return qs.count()


def children_of(location_id, level=None):
    """Direct sub-areas (LocationImport rows) of an area, ordered by name."""
    level = level or level_of(location_id)
    child = CHILD_LEVEL.get(level)
    if not child:
        return []
    qs = LocationImport.objects.filter(type=TYPE_OF_LEVEL[child]).annotate(_s=Cast('location_id', TextField()))
    prefix = prefix_of(location_id)
    if prefix:
        qs = qs.filter(_s__startswith=prefix)
    return list(qs.filter(location_id__gt=0).order_by('name'))


def _cached(key, compute):
    value = cache.get(key)
    if value is None:
        value = compute()
        cache.set(key, value, CACHE_SECONDS)
    return value


def clear_cache():
    """Call after load_census so the next request sees the new figures."""
    cache.delete_many([f'census:{k}' for k in ('datasets',)])
    cache.clear()


class Estimator:
    """Population estimates for areas. `preload` fetches, in a few queries, everything a chain of areas and their
    sub-areas need; the per-item lookups fall back to single queries for anything not preloaded."""

    def __init__(self, year=None):
        self.year = int(year) if year else timezone.localdate().year
        self._villages = {}        # prefix -> number of villages under it
        self._figures = {}         # (location, kind, year) -> PopulationFigure or None
        self._names = {}           # location -> name
        self._loaded = set()       # locations whose PopulationFigure rows are all in self._rows
        self._rows = {}            # location -> [PopulationFigure]
        self._root = None          # prefix under which village ids and registered counts are preloaded
        self._village_ids = None   # [str id] of every village under the root
        self._registered = None    # {village id (str): living citizens} under the root
        self._households = {}      # sector -> households count from the census indicators

    # --- bulk loading ---
    def preload(self, locations, root=None):
        """Load names and population figures for `locations` and, under `root`, every village id and the
        registered-citizen count per village, so later lookups need no further queries."""
        locations = {int(loc) for loc in locations}
        self._names.update(LocationImport.objects.filter(location_id__in=locations).values_list('location_id', 'name'))
        for loc in locations:
            self._rows.setdefault(loc, [])
        for fig in PopulationFigure.objects.filter(location__in=locations):
            self._rows[fig.location].append(fig)
        self._loaded |= locations
        sectors = [loc for loc in locations if level_of(loc) == 'sector']
        if sectors:
            self._households.update(
                CensusIndicator.objects.filter(location__in=sectors, year=CENSUS_YEAR, key='households')
                .values_list('location', 'value'))
        if root is not None:
            prefix = prefix_of(root)
            villages = LocationImport.objects.filter(type='VILLAGE', location_id__gt=0) \
                .annotate(_s=Cast('location_id', TextField()))
            citizens = Citizen.objects.filter(status='alive').annotate(_v=Cast('village', TextField()))
            if prefix:
                villages = villages.filter(_s__startswith=prefix)
                citizens = citizens.filter(_v__startswith=prefix)
            self._root = prefix
            self._village_ids = [str(v) for v in villages.values_list('location_id', flat=True)]
            self._registered = {str(r['village']): r['n'] for r in citizens.values('village').annotate(n=Count('id'))}

    # --- lookups ---
    def name(self, location_id):
        location_id = int(location_id)
        if location_id not in self._names:
            self._names[location_id] = area_name(location_id)
        return self._names[location_id]

    def villages_under(self, location_id):
        key = prefix_of(location_id)
        if key not in self._villages:
            if self._village_ids is not None and key.startswith(self._root):
                self._villages[key] = sum(1 for v in self._village_ids if v.startswith(key))
            else:
                qs = LocationImport.objects.filter(type='VILLAGE').annotate(_s=Cast('location_id', TextField()))
                if key:
                    qs = qs.filter(_s__startswith=key)
                self._villages[key] = qs.count()
        return self._villages[key]

    def registered(self, location_id):
        key = prefix_of(location_id)
        if self._registered is not None and key.startswith(self._root):
            return sum(n for v, n in self._registered.items() if v.startswith(key))
        return registered_count(location_id)

    def figure(self, location_id, kind, year=None):
        """A population figure of one kind: the exact year when given, else the latest year on file."""
        location_id = int(location_id)
        key = (location_id, kind, year)
        if key not in self._figures:
            if location_id in self._loaded:
                rows = [r for r in self._rows[location_id] if r.kind == kind and (year is None or r.year == year)]
                self._figures[key] = max(rows, key=lambda r: r.year) if rows else None
            else:
                qs = PopulationFigure.objects.filter(location=location_id, kind=kind)
                if year:
                    qs = qs.filter(year=year)
                self._figures[key] = qs.order_by('-year').first()
        return self._figures[key]

    def district_total(self, district_id, year):
        """District population in a year: the census for 2022, NISR's projection for the year or, beyond the
        published years, the latest projected year before it (e.g. 2032 for 2040)."""
        if year <= CENSUS_YEAR:
            fig = self.figure(district_id, 'census', CENSUS_YEAR)
            return fig.total if fig else None
        district_id = int(district_id)
        key = (district_id, 'projection<=', year)
        if key not in self._figures:
            if district_id in self._loaded:
                rows = [r for r in self._rows[district_id] if r.kind == 'projection' and r.year <= year]
                self._figures[key] = max(rows, key=lambda r: r.year) if rows else None
            else:
                self._figures[key] = PopulationFigure.objects.filter(
                    location=district_id, kind='projection', year__lte=year).order_by('-year').first()
        fig = self._figures[key]
        return fig.total if fig else None

    def growth(self, district_id, from_year, to_year):
        """Multiplier that carries a count from one year to another along the district's projection."""
        if from_year == to_year or not district_id:
            return 1.0
        a, b = self.district_total(district_id, from_year), self.district_total(district_id, to_year)
        if not a or not b:
            return None
        return b / a

    def sector_households(self, sector_id):
        sector_id = int(sector_id)
        if sector_id not in self._households:
            row = CensusIndicator.objects.filter(location=sector_id, year=CENSUS_YEAR, key='households').first()
            self._households[sector_id] = row.value if row else None
        return self._households[sector_id]

    # --- estimates ---
    def estimate(self, location_id):
        """Population estimate for one area. Returns None when nothing is known about it."""
        location_id = int(location_id)
        level = level_of(location_id)
        if level is None:
            return None
        chain = chain_of(location_id)
        district = chain.get('district')
        sector = chain.get('sector')
        out = {
            'location': location_id, 'level': level, 'name': self.name(location_id),
            'year': self.year, 'census_year': CENSUS_YEAR, 'census': None, 'estimate': None,
            'male': None, 'female': None, 'households': None, 'share': None,
            'method': None, 'basis': '', 'source': '', 'local_count': None,
        }

        census = self.figure(location_id, 'census', CENSUS_YEAR)
        base_total, base_year = None, CENSUS_YEAR
        if census:
            out.update(census=census.total, male=census.male, female=census.female, households=census.households,
                       method='census', source=census.source or SOURCE_CENSUS,
                       basis='Counted by the 2022 census.')
            base_total = census.total
        elif level in ('cell', 'village') and sector:
            sector_fig = self.figure(sector, 'census', CENSUS_YEAR)
            n_sector = self.villages_under(sector)
            n_here = 1 if level == 'village' else self.villages_under(location_id)
            if sector_fig and n_sector:
                share = n_here / n_sector
                base_total = round(sector_fig.total * share)
                hh = self.sector_households(sector)
                out.update(
                    census=base_total, share=round(share, 5), method='derived', source=SOURCE_CENSUS,
                    male=round(sector_fig.male * share) if sector_fig.male else None,
                    female=round(sector_fig.female * share) if sector_fig.female else None,
                    households=round(hh * share) if hh else None,
                    basis=(f'{self.name(sector)} sector counted {sector_fig.total:,} people in 2022, shared equally '
                           f'among its {n_sector} villages ({n_here} here).'),
                )

        manual = self.figure(location_id, 'manual')
        if manual:
            out['local_count'] = {
                'total': manual.total, 'households': manual.households, 'year': manual.year, 'note': manual.note,
                'updated_at': manual.updated_at, 'updated_by': manual.updated_by.display_name if manual.updated_by else '',
            }
            base_total, base_year = manual.total, manual.year
            out.update(method='local', households=manual.households or out['households'],
                       basis=f'Local count of {manual.total:,} entered for {manual.year}'
                             + (f' ({manual.note})' if manual.note else '') + '.')
            if manual.male is not None:
                out.update(male=manual.male, female=manual.female)

        if base_total is None:
            return out

        growth = self.growth(district, base_year, self.year)
        if growth is None:
            growth = 1.0
        out['estimate'] = round(base_total * growth)
        if growth != 1.0:
            out['basis'] += f' Grown to {self.year} with the NISR district projection (×{growth:.3f}).'
        return out

    def coverage_row(self, location_id):
        row = self.estimate(location_id) or {'location': int(location_id), 'level': level_of(location_id),
                                              'name': self.name(location_id), 'estimate': None, 'census': None}
        registered = self.registered(location_id)
        row['registered'] = registered
        est = row.get('estimate')
        row['coverage_pct'] = round(100 * registered / est, 1) if est else None
        row['gap'] = (est - registered) if est is not None else None
        return row

    def coverage(self, location_id, with_children=True):
        """Rows for the area and every area above it up to the district, plus its direct sub-areas."""
        location_id = int(location_id)
        level = level_of(location_id)
        chain = chain_of(location_id)
        upward = [lvl for lvl in ('village', 'cell', 'sector', 'district') if lvl in chain
                  and LEVELS.index(lvl) <= LEVELS.index(level)] if level in ('village', 'cell', 'sector', 'district') \
            else [level]
        children = children_of(location_id, level) if with_children else []

        # One round of bulk queries for every area the rows below touch
        wanted = {chain[lvl] for lvl in upward} | {c.location_id for c in children}
        for loc in list(wanted):
            wanted |= {v for k, v in chain_of(loc).items() if k in ('sector', 'district')}
        self.preload(wanted, root=chain.get('district', location_id))
        for c in children:
            self._names[c.location_id] = c.name

        rows = [self.coverage_row(chain[lvl]) for lvl in upward]
        return {
            'location': location_id, 'level': level, 'name': self.name(location_id), 'year': self.year,
            'census_year': CENSUS_YEAR, 'chain': rows, 'child_level': CHILD_LEVEL.get(level),
            'children': [self.coverage_row(c.location_id) for c in children],
            'methods': {
                'census': 'Counted by NISR in the 2022 census.',
                'derived': 'Sector census population shared equally among its villages (NISR publishes no cell or '
                           'village counts).',
                'local': 'A local count entered by a leader replaces the derived estimate.',
            },
        }


def _indicator_rows(rows):
    out = []
    for r in rows:
        label, unit, group = INDICATORS.get(r.key, (r.key.replace('_', ' ').capitalize(), 'count', 'Other'))
        out.append({'key': r.key, 'label': label, 'unit': unit, 'group': group, 'value': r.value, 'source': r.source})
    return out


def indicators_for(location_id, year=CENSUS_YEAR):
    """Published indicators for one area as a list of {key, label, unit, group, value}."""
    return indicators_for_many([location_id], year).get(int(location_id), [])


def indicators_for_many(locations, year=CENSUS_YEAR):
    """{location: [indicator rows]} for several areas in one query (cached)."""
    locations = sorted({int(loc) for loc in locations})

    def compute():
        out = {loc: [] for loc in locations}
        for r in CensusIndicator.objects.filter(location__in=locations, year=year).order_by('key'):
            out[r.location].append(r)
        return {loc: _indicator_rows(rows) for loc, rows in out.items()}

    return _cached(f'census:indicators:{year}:{",".join(map(str, locations))}', compute)


def projections_for(district_id):
    def compute():
        figs = PopulationFigure.objects.filter(location=district_id, kind='projection').order_by('year')
        bands = {}
        for ind in CensusIndicator.objects.filter(location=district_id, year__gte=PROJECTION_YEARS[0],
                                                  key__in=['children_0_17', 'youth_16_30', 'working_16_64',
                                                           'elderly_60plus', 'school_6_17', 'under_5']):
            bands.setdefault(ind.year, {})[ind.key] = int(ind.value)
        return [{'year': f.year, 'total': f.total, 'male': f.male, 'female': f.female, **bands.get(f.year, {})}
                for f in figs]

    return _cached(f'census:projections:{int(district_id)}', compute)


def dataset_summary():
    """What is loaded, for the Census page: one line per source and kind (three aggregate queries, cached)."""
    def years(lo, hi):
        return f'{lo}–{hi}' if lo != hi else str(lo)

    def compute():
        out = []
        labels = dict(PopulationFigure.KIND_CHOICES)
        groups = {}
        for r in PopulationFigure.objects.values('kind', 'source', 'level').annotate(n=Count('id'), lo=Min('year'),
                                                                                    hi=Max('year')):
            g = groups.setdefault((r['kind'], r['source']), {'rows': 0, 'levels': set(), 'lo': r['lo'], 'hi': r['hi']})
            g['rows'] += r['n']
            g['levels'].add(r['level'])
            g['lo'], g['hi'] = min(g['lo'], r['lo']), max(g['hi'], r['hi'])
        for (kind, source), g in sorted(groups.items()):
            out.append({'dataset': f'Population figures: {labels[kind].lower()}', 'rows': g['rows'],
                        'years': years(g['lo'], g['hi']), 'levels': sorted(g['levels'], key=LEVELS.index), 'source': source})
        levels = {}
        for r in CensusIndicator.objects.values('source', 'level').annotate(n=Count('id')):
            levels.setdefault(r['source'], set()).add(r['level'])
        for r in CensusIndicator.objects.values('source').annotate(n=Count('id'), kinds=Count('key', distinct=True),
                                                                   lo=Min('year'), hi=Max('year')).order_by('source'):
            out.append({'dataset': f"Indicators ({r['kinds']} kinds)", 'rows': r['n'], 'years': years(r['lo'], r['hi']),
                        'levels': sorted(levels.get(r['source'], ()), key=LEVELS.index), 'source': r['source']})
        return out

    return _cached('census:datasets', compute)
