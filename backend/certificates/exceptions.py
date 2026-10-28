"""API error handling: every failure reaches the frontend as JSON with a readable `detail`, never as an HTML page."""
import logging
import traceback

from django.conf import settings
from django.db import DatabaseError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger('certify.api')


def api_exception_handler(exc, context):
    # DRF's own exceptions (validation, permission, 404…) already come back as JSON
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    view = context.get('view')
    where = f'{view.__class__.__module__}.{view.__class__.__name__}' if view else 'unknown view'
    request = context.get('request')
    path = getattr(request, 'path', '')
    log.error('Unhandled error in %s %s (%s): %s\n%s', getattr(request, 'method', ''), path, where, exc,
              traceback.format_exc())

    if isinstance(exc, DatabaseError):
        detail = 'The database could not be reached or the query failed.'
        code = 'database_error'
    else:
        detail = 'The server hit an unexpected error while handling this request.'
        code = 'server_error'
    body = {'detail': detail, 'code': code}
    if settings.DEBUG:
        # Developers see the real exception; production users only the generic sentence
        body['error'] = f'{exc.__class__.__name__}: {exc}'
        body['traceback'] = traceback.format_exc().splitlines()[-12:]
    return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
