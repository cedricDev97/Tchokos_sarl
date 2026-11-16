"""Readiness probe non authentifiée : vérifie uniquement la connexion DB.

Aucune donnée métier ni détail d'erreur n'est révélé au public.
"""
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if not row or row[0] != 1:
                raise DatabaseError("readiness query returned no result")
    except DatabaseError:
        response = HttpResponse("unavailable", status=503, content_type="text/plain")
    else:
        response = HttpResponse("ok", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response
