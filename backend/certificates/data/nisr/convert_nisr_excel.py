"""Convert the NISR (National Institute of Statistics of Rwanda) census workbooks into the CSV files next to this script.

The CSVs are what `manage.py load_census` imports; this converter only needs to run again when NISR publishes new
workbooks. It needs `openpyxl` and `xlrd` (not runtime requirements):

    pip install openpyxl xlrd
    python convert_nisr_excel.py <folder with the downloaded workbooks> [<output folder>]

Expected workbook file names inside the download folder (see SOURCES.md for the download links):
    pop_size.xlsx  main_indicators.xlsx  children.xlsx  elderly.xls  disability.xlsx  housing.xlsx  education.xlsx
    poverty.xls  projections.xls  proj/<District>.xlsx (one per district, single-age projections 2023-2032)
"""
import csv
import os
import sys

import openpyxl
import xlrd

DISTRICTS = [
    'Nyarugenge', 'Gasabo', 'Kicukiro',
    'Nyanza', 'Gisagara', 'Nyaruguru', 'Huye', 'Nyamagabe', 'Ruhango', 'Muhanga', 'Kamonyi',
    'Karongi', 'Rutsiro', 'Rubavu', 'Nyabihu', 'Ngororero', 'Rusizi', 'Nyamasheke',
    'Rulindo', 'Gakenke', 'Musanze', 'Burera', 'Gicumbi',
    'Rwamagana', 'Nyagatare', 'Gatsibo', 'Kayonza', 'Kirehe', 'Ngoma', 'Bugesera',
]
DISTRICT_LOWER = [d.lower() for d in DISTRICTS]
# Province spellings used across the workbooks -> canonical name
PROVINCES = {
    'city of kigali': 'City of Kigali', 'kigali city': 'City of Kigali', 'cok': 'City of Kigali',
    'southern province': 'Southern Province', 'south': 'Southern Province',
    'western province': 'Western Province', 'west': 'Western Province',
    'northern province': 'Northern Province', 'north': 'Northern Province',
    'eastern province': 'Eastern Province', 'east': 'Eastern Province',
}
NATIONAL = {'rwanda', 'national', 'total'}


def clean(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).replace('\xa0', ' ').strip()


def rows_of(path, sheet):
    """Every row of a sheet as a list of trimmed strings (works for .xlsx and .xls)."""
    if path.endswith('.xlsx'):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        return [[clean(c) for c in r] for r in wb[sheet].iter_rows(values_only=True)]
    wb = xlrd.open_workbook(path)
    ws = wb.sheet_by_name(sheet)
    return [[clean(c.value) for c in ws.row(r)] for r in range(ws.nrows)]


def number(s):
    try:
        return float(s.replace(',', ''))
    except (ValueError, AttributeError):
        return None


def split_row(row):
    """(name, [numbers]) where name is the first text cell and numbers every numeric cell after it."""
    name, nums, seen = '', [], False
    for cell in row:
        if not seen:
            if cell and number(cell) is None:
                name, seen = cell.strip(), True
            continue
        n = number(cell)
        if n is not None:
            nums.append(n)
        elif cell == '':
            nums.append(None)   # blank cells keep their position (e.g. no urban population)
    while nums and nums[-1] is None:
        nums.pop()
    return name, nums


def norm(s):
    return ' '.join(s.lower().replace('’', "'").replace('*', '').split())


def sector_rows(path, sheet):
    """Yield (district, sector, numbers) for every sector row of a 'by sector of residence' table."""
    district = None
    for row in rows_of(path, sheet):
        name, nums = split_row(row)
        if not name:
            continue
        key = norm(name)
        has_numbers = any(n is not None for n in nums)
        if key in DISTRICT_LOWER and not has_numbers:
            district = DISTRICTS[DISTRICT_LOWER.index(key)]
            continue
        if key in NATIONAL or key in PROVINCES or key.startswith('source') or key.startswith('table'):
            continue
        if district and has_numbers:
            yield district, name, nums


def district_rows(path, sheet):
    """Yield (level, name, numbers) for national / province / district rows of a 'by province and district' table."""
    for row in rows_of(path, sheet):
        name, nums = split_row(row)
        if not name or not any(n is not None for n in nums):
            continue
        key = norm(name)
        if key in DISTRICT_LOWER:
            yield 'district', DISTRICTS[DISTRICT_LOWER.index(key)], nums
        elif key in PROVINCES:
            yield 'province', PROVINCES[key], nums
        elif key == 'rwanda':
            yield 'country', 'Rwanda', nums


def at(nums, i, scale=1):
    try:
        v = nums[i]
    except IndexError:
        return None
    return None if v is None else round(v * scale, 4)


def write_csv(out_dir, name, header, data):
    path = os.path.join(out_dir, name)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in data:
            w.writerow(['' if v is None else v for v in r])
    print(f'{name}: {len(data)} rows')


def main(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    def p(f):
        return os.path.join(src, f)

    # --- Sector resident population 2022 (Population size thematic report, Table D1) ---
    pop = []
    for district, sector, n in sector_rows(p('pop_size.xlsx'), 'Table D1'):
        pop.append([district, sector, at(n, 0), at(n, 1), at(n, 2), at(n, 3), at(n, 6)])
    write_csv(out_dir, 'sector_population_2022.csv',
              ['district', 'sector', 'total', 'male', 'female', 'urban', 'rural'], pop)

    # --- Sector indicators 2022 (long format) ---
    ind = []

    def add(district, sector, key, value):
        if value is not None:
            ind.append([district, sector, key, value])

    for d, s, n in sector_rows(p('children.xlsx'), 'TableB1'):
        add(d, s, 'children_0_17', at(n, 2))
        add(d, s, 'children_share_pct', at(n, 5))
    for d, s, n in sector_rows(p('elderly.xls'), 'Table 22'):
        add(d, s, 'elderly_60plus', at(n, 2))
        add(d, s, 'elderly_share_pct', at(n, 8))
    for d, s, n in sector_rows(p('disability.xlsx'), 'Table D.1'):
        add(d, s, 'disabled_5plus', at(n, 2))
        add(d, s, 'pop_5plus', at(n, 3))
        if len(n) > 3 and n[2] is not None and n[3]:
            add(d, s, 'disability_prevalence_pct', round(100 * n[2] / n[3], 2))
    for d, s, n in sector_rows(p('housing.xlsx'), 'Table-C1.1'):
        add(d, s, 'households', at(n, -1))
        add(d, s, 'hh_umudugudu_pct', at(n, 0, 100))
        add(d, s, 'hh_modern_planned_pct', at(n, 4, 100))
        add(d, s, 'hh_spontaneous_pct', at(n, 5, 100))
    for d, s, n in sector_rows(p('housing.xlsx'), 'Table-C1.2'):
        add(d, s, 'hh_improved_water_pct', round(100 * sum(v or 0 for v in n[:9]), 2))
    for d, s, n in sector_rows(p('housing.xlsx'), 'Table-C1.3'):
        add(d, s, 'hh_electricity_pct', at(n, 0, 100))
    for d, s, n in sector_rows(p('housing.xlsx'), 'Table-C1.4'):
        for i, key in enumerate(['hh_radio_pct', 'hh_tv_pct', 'hh_mobile_pct', 'hh_smartphone_pct', 'hh_computer_pct',
                                 'hh_bicycle_pct', 'hh_motorcycle_pct', 'hh_vehicle_pct']):
            add(d, s, key, at(n, i, 100))
    for d, s, n in sector_rows(p('education.xlsx'), 'Table C. 35'):
        add(d, s, 'pop_12plus', at(n, -1))
        add(d, s, 'edu_no_primary_pct', at(n, 0))
        add(d, s, 'edu_secondary_plus_pct', round(sum(v or 0 for v in n[3:9]), 1))
        add(d, s, 'edu_tertiary_pct', round(sum(v or 0 for v in n[5:9]), 1))
    for d, s, n in sector_rows(p('poverty.xls'), 'Table_C_1'):
        for i, key in enumerate(['poverty_nonpoor_pct', 'poverty_vulnerable_pct', 'poverty_moderate_pct',
                                 'poverty_severe_pct']):
            add(d, s, key, at(n, i))
    for d, s, n in sector_rows(p('poverty.xls'), 'Table_C_10'):
        add(d, s, 'mpi_headcount_pct', at(n, 0, 100))
        add(d, s, 'mpi_index', at(n, 2))
    write_csv(out_dir, 'sector_indicators_2022.csv', ['district', 'sector', 'key', 'value'], ind)

    # --- Country / province / district population 2022 (Main Indicators Tables 1, 2, 38, 44, 47, 49, 54) ---
    mi = p('main_indicators.xlsx')
    base = {}
    for level, name, n in district_rows(mi, 'Table 1'):
        base[(level, name)] = {'total': at(n, 0), 'male': at(n, 1), 'female': at(n, 2), 'density': at(n, 4)}
    for level, name, n in district_rows(mi, 'Table 2'):
        base.setdefault((level, name), {}).update({'urban': at(n, 1), 'rural': at(n, 2)})
    for sheet, key in [('Table 38', 'children_0_17'), ('Table 44', 'youth_16_30'), ('Table 47', 'women'),
                       ('Table 49', 'elderly_60plus'), ('Table 54', 'disabled_5plus')]:
        for level, name, n in district_rows(mi, sheet):
            base.setdefault((level, name), {})[key] = at(n, 0)
    cols = ['total', 'male', 'female', 'urban', 'rural', 'density', 'children_0_17', 'youth_16_30', 'women',
            'elderly_60plus', 'disabled_5plus']
    write_csv(out_dir, 'area_population_2022.csv', ['level', 'name'] + cols,
              [[level, name] + [vals.get(c) for c in cols] for (level, name), vals in base.items()])

    # --- Country / province / district indicators 2022 (long format) ---
    dind = []

    def dadd(level, name, key, value):
        if value is not None:
            dind.append([level, name, key, value])

    simple = [
        ('Table 2', 'urban_share_pct', 4), ('Table 21', 'internet_10plus_pct', 0), ('Table 21', 'internet_16plus_pct', 3),
        ('Table 25', 'hh_mobile_pct', 0), ('Table 28', 'medical_insurance_pct', 0),
        ('Table 32', 'net_lifetime_migration', 3), ('Table 32', 'net_recent_migration', 6),
        ('Table 39', 'children_share_pct', 0), ('Table 40', 'birth_registration_pct', 0),
        ('Table 45', 'youth_share_pct', 0), ('Table 47', 'women_share_pct', 1), ('Table 48', 'female_headship_pct', 0),
        ('Table 50', 'elderly_share_pct', 0), ('Table 54', 'disability_prevalence_pct', 3),
    ]
    for sheet, key, col in simple:
        for level, name, n in district_rows(mi, sheet):
            dadd(level, name, key, at(n, col))
    for level, name, n in district_rows(p('pop_size.xlsx'), 'Table 4.4 '):
        dadd(level, name, 'mean_age', at(n, 2))
        dadd(level, name, 'median_age', at(n, 5))
    write_csv(out_dir, 'area_indicators_2022.csv', ['level', 'name', 'key', 'value'], dind)

    # --- District projections 2023-2032 by single age -> yearly totals and age bands ---
    proj = []
    bands = {'children_0_17': (0, 17), 'youth_16_30': (16, 30), 'working_16_64': (16, 64),
             'elderly_60plus': (60, 200), 'school_6_17': (6, 17), 'under_5': (0, 4)}
    for district in DISTRICTS:
        path = os.path.join(src, 'proj', f'{district}.xlsx')
        if not os.path.exists(path):
            print(f'  missing projection workbook for {district}', file=sys.stderr)
            continue
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = [[clean(c) for c in r] for r in wb.worksheets[0].iter_rows(values_only=True)]
        year_row = next(r for r in rows if any(c.isdigit() and len(c) == 4 for c in r))
        years = [(i, int(c)) for i, c in enumerate(year_row) if c.isdigit() and len(c) == 4]
        ages = []
        for r in rows:
            label = r[0].rstrip('+') if r else ''
            if label.isdigit():
                ages.append((int(label), r))

        def total(col, lo, hi, offset=0):
            return int(sum(number(r[col + offset]) or 0 for a, r in ages if lo <= a <= hi))

        for col, year in years:
            rec = [district, year, total(col, 0, 200), total(col, 0, 200, 1), total(col, 0, 200, 2)]
            rec += [total(col, lo, hi) for lo, hi in bands.values()]
            proj.append(rec)
    write_csv(out_dir, 'district_projections_2023_2032.csv',
              ['district', 'year', 'total', 'male', 'female'] + list(bands.keys()), proj)

    # --- National projections 2022-2052 (Population projection thematic report, Table 7) ---
    nat = []
    for row in rows_of(p('projections.xls'), 'Table 7'):
        nums = [number(c) for c in row]
        nums = [v for v in nums if v is not None]
        if len(nums) >= 4 and 2000 < nums[0] < 2100:
            nat.append([int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])])
    write_csv(out_dir, 'national_projections_2022_2052.csv', ['year', 'high', 'medium', 'low'], nat)

    # --- National age structure 2022 (Main Indicators Table 5) ---
    age = []
    for row in rows_of(mi, 'Table 5'):
        name, n = split_row(row)
        if name and (name[0].isdigit() or name.lower() == 'total') and len(n) >= 9:
            age.append([name.replace(' ', ''), at(n, 0), at(n, 1), at(n, 2), at(n, 3), at(n, 6)])
    write_csv(out_dir, 'national_age_groups_2022.csv', ['age_group', 'total', 'male', 'female', 'urban', 'rural'], age)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__)))
