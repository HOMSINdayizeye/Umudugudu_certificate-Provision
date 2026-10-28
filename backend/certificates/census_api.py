"""Census endpoints: registration coverage against NISR population figures, published indicators, local counts."""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import LocationImport, PopulationFigure
from .permissions import has_perm, is_full_admin
from . import census


def user_scope(user):
    """Most specific area an account belongs to or leads."""
    return user.scope_code or user.village or user.cell or user.sector or user.district or user.province


def related(location, scope):
    # The area is inside the user's area, or is one of the areas above it (its cell, sector, district…)
    if scope is None:
        return False
    a, b = str(int(location)), str(int(scope))
    return int(location) == 0 or a.startswith(b) or b.startswith(a)


def can_view(user, location):
    if is_full_admin(user):
        return True
    return has_perm(user, 'view:census') and related(location, user_scope(user))


def parse_location(request):
    raw = request.GET.get('location') if request.method == 'GET' else request.data.get('location')
    if raw in (None, ''):
        return user_scope(request.user), None
    try:
        location = int(raw)
    except (TypeError, ValueError):
        return None, Response({'detail': 'location must be a location id.'}, status=status.HTTP_400_BAD_REQUEST)
    if not (location == 0 or LocationImport.objects.filter(location_id=location).exists()):
        return None, Response({'detail': 'Unknown location.'}, status=status.HTTP_404_NOT_FOUND)
    return location, None


def parse_year(request):
    try:
        return int(request.GET.get('year') or timezone.localdate().year)
    except ValueError:
        return timezone.localdate().year


@api_view(['GET'])
def census_coverage(request):
    """Registered citizens vs estimated population for an area, the areas above it and its sub-areas.

    ?location=<id> (defaults to the signed-in user's own area) &year=<yyyy> (defaults to this year)
    """
    location, error = parse_location(request)
    if error:
        return error
    if location is None:
        return Response({'detail': 'Your account has no area assigned.'}, status=status.HTTP_400_BAD_REQUEST)
    if not can_view(request.user, location):
        return Response({'detail': 'You may only see the coverage of your own area.'}, status=status.HTTP_403_FORBIDDEN)
    estimator = census.Estimator(parse_year(request))
    data = estimator.coverage(location, with_children=request.GET.get('children', '1') != '0')
    data['can_manage'] = is_full_admin(request.user) or has_perm(request.user, 'manage:census')
    return Response(data)


@api_view(['GET'])
def census_area(request):
    """Published NISR figures for an area: its estimate, the indicators of its sector, district, province and country,
    and the district's 2023-2032 projections."""
    location, error = parse_location(request)
    if error:
        return error
    if location is None:
        location = 0
    if not (is_full_admin(request.user) or has_perm(request.user, 'view:census')):
        return Response({'detail': 'You are not allowed to view census data.'}, status=status.HTTP_403_FORBIDDEN)
    estimator = census.Estimator(parse_year(request))
    chain = census.chain_of(location)
    # Everything the page needs for the chain comes from a few bulk (and cached) queries
    estimator.preload(set(chain.values()) | {location})
    levels = [lvl for lvl in ('sector', 'district', 'province', 'country') if lvl in chain]
    indicators = census.indicators_for_many([chain[lvl] for lvl in levels])
    areas = []
    for level in levels:
        loc = chain[level]
        fig = estimator.figure(loc, 'census', census.CENSUS_YEAR)
        areas.append({
            'level': level, 'location': loc, 'name': estimator.name(loc),
            'population': {'total': fig.total, 'male': fig.male, 'female': fig.female, 'urban': fig.urban,
                           'rural': fig.rural, 'households': fig.households} if fig else None,
            'indicators': indicators.get(loc, []),
        })
    return Response({
        'location': location, 'level': census.level_of(location), 'name': census.area_name(location),
        'estimate': estimator.estimate(location),
        'areas': areas,
        'projections': census.projections_for(chain['district']) if 'district' in chain else [],
        'census_year': census.CENSUS_YEAR,
    })


@api_view(['PUT', 'DELETE'])
def census_local_count(request):
    """Enter (PUT) or remove (DELETE) a leader's local population count for a cell or village.

    PUT body: {location, total, households?, year?, note?}
    DELETE: ?location=<id>&year=<yyyy>
    """
    user = request.user
    if not (is_full_admin(user) or has_perm(user, 'manage:census')):
        return Response({'detail': 'You are not allowed to enter population counts.'}, status=status.HTTP_403_FORBIDDEN)
    location, error = parse_location(request)
    if error:
        return error
    if location is None:
        return Response({'detail': 'location is required.'}, status=status.HTTP_400_BAD_REQUEST)
    level = census.level_of(location)
    if level not in ('cell', 'village'):
        return Response({'detail': 'Local counts are kept for cells and villages only; NISR publishes the rest.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not is_full_admin(user) and not str(location).startswith(str(user_scope(user) or 'x')):
        return Response({'detail': 'You may only enter counts for areas inside your own.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'DELETE':
        year = request.GET.get('year')
        qs = PopulationFigure.objects.filter(location=location, kind='manual')
        if year:
            qs = qs.filter(year=year)
        deleted = qs.delete()[0]
        return Response({'detail': f'{deleted} local count(s) removed.', 'coverage': census.Estimator().coverage_row(location)})

    try:
        total = int(request.data.get('total'))
        households = request.data.get('households')
        households = int(households) if households not in (None, '') else None
        year = int(request.data.get('year') or timezone.localdate().year)
    except (TypeError, ValueError):
        return Response({'detail': 'total, households and year must be whole numbers.'}, status=status.HTTP_400_BAD_REQUEST)
    if total < 0 or (households is not None and households < 0):
        return Response({'detail': 'Counts cannot be negative.'}, status=status.HTTP_400_BAD_REQUEST)
    if not census.CENSUS_YEAR <= year <= timezone.localdate().year + 1:
        return Response({'detail': f'year must be between {census.CENSUS_YEAR} and next year.'},
                        status=status.HTTP_400_BAD_REQUEST)
    PopulationFigure.objects.update_or_create(
        location=location, year=year, kind='manual',
        defaults={'level': level, 'total': total, 'households': households, 'note': (request.data.get('note') or '')[:500],
                  'source': f'Local count by {user.display_name}', 'updated_by': user})
    return Response({'detail': 'Local count saved.', 'coverage': census.Estimator().coverage_row(location)})


@api_view(['GET'])
def census_datasets(request):
    if not (is_full_admin(request.user) or has_perm(request.user, 'view:census')):
        return Response({'detail': 'You are not allowed to view census data.'}, status=status.HTTP_403_FORBIDDEN)
    return Response({'datasets': census.dataset_summary(), 'indicators': [
        {'key': k, 'label': label, 'unit': unit, 'group': group} for k, (label, unit, group) in census.INDICATORS.items()]})
