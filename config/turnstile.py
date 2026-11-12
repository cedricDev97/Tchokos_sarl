"""Cloudflare Turnstile : validation serveur lorsque la protection est activée."""
import json
from urllib import parse, request as http_request
from django.conf import settings
from django.http import JsonResponse

def verify_turnstile(request, data, action):
    if not settings.EKAKO_TURNSTILE_ENABLED:
        return None
    token = data.get("turnstile_token", "") if isinstance(data, dict) else ""
    if not isinstance(token, str) or not 1 <= len(token) <= 2048:
        return JsonResponse({"ok": False, "error": "Vérification anti-robot requise."}, status=400)
    body = parse.urlencode({"secret": settings.EKAKO_TURNSTILE_SECRET_KEY, "response": token}).encode()
    req = http_request.Request("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=body, method="POST")
    try:
        with http_request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read(16384))
    except (OSError, ValueError):
        return JsonResponse({"ok": False, "error": "Vérification anti-robot indisponible. Réessayez."}, status=503)
    if result.get("success") is not True or result.get("action") != action:
        return JsonResponse({"ok": False, "error": "Vérification anti-robot échouée."}, status=400)
    expected = settings.EKAKO_TURNSTILE_HOSTNAME
    if expected and result.get("hostname", "").lower() != expected:
        return JsonResponse({"ok": False, "error": "Origine de vérification incorrecte."}, status=400)
    return None
