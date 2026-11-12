"""Validation serveur de Cloudflare Turnstile (fail-closed si actif).

Les clés de test officielles n'incluent pas `action` dans le résultat Siteverify.
Seul DEBUG=True ET une paire de clés de test connues autorisent cette exception.
"""
import json
from urllib import parse, request as http_request

from django.conf import settings
from django.http import JsonResponse

_TEST_SITE_KEYS = frozenset({
    "1x00000000000000000000AA",  # succès
    "2x00000000000000000000AB",  # échec
    "3x00000000000000000000FF",  # interactif
})
_TEST_SECRET_KEYS = frozenset({
    "1x0000000000000000000000000000000AA",
    "2x0000000000000000000000000000000AA",
    "3x0000000000000000000000000000000AA",
})


def verify_turnstile(request, data, action):
    """Renvoie None en cas de succès ou une erreur JSON HTTP 400/503."""
    if not settings.EKAKO_TURNSTILE_ENABLED:
        return None

    token = data.get("turnstile_token", "") if isinstance(data, dict) else ""
    if not isinstance(token, str) or not 1 <= len(token) <= 2048:
        return JsonResponse(
            {"ok": False, "error": "Vérification anti-robot requise."},
            status=400,
        )

    params = parse.urlencode({
        "secret": settings.EKAKO_TURNSTILE_SECRET_KEY,
        "response": token,
    }).encode("utf-8")
    req = http_request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=params, method="POST",
    )
    try:
        with http_request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read(16384).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Vérification anti-robot indisponible. Réessayez."},
            status=503,
        )

    if not isinstance(result, dict) or result.get("success") is not True:
        return JsonResponse(
            {"ok": False, "error": "Vérification anti-robot échouée. Réessayez."},
            status=400,
        )

    is_local_test = (
        settings.DEBUG
        and settings.EKAKO_TURNSTILE_SITE_KEY in _TEST_SITE_KEYS
        and settings.EKAKO_TURNSTILE_SECRET_KEY in _TEST_SECRET_KEYS
    )

    # Siteverify avec clés de test renvoie hostname=example.com, sans action.
    if not is_local_test:
        if result.get("action") != action:
            return JsonResponse(
                {"ok": False, "error": "Action anti-robot non conforme."},
                status=400,
            )
        hostname = str(result.get("hostname") or "").lower()
        expected = settings.EKAKO_TURNSTILE_HOSTNAME
        if expected and hostname != expected:
            return JsonResponse(
                {"ok": False, "error": "Origine de vérification incorrecte."},
                status=400,
            )
    return None
