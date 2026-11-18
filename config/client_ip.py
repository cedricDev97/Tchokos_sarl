"""Résolution prudente de l'IP pour les limites anti-abus eKAKO.

Par défaut, seule REMOTE_ADDR est utilisée. L'en-tête Cloudflare n'est
accepté que lorsque l'exploitant a explicitement vérifié la chaîne proxy
et activé EKAKO_CLIENT_IP_SOURCE=cloudflare sur son service Render.
Ne jamais prendre la première adresse X-Forwarded-For côté client.
"""
from ipaddress import ip_address

from django.conf import settings


def _ip(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    value = value.strip()
    try:
        return ip_address(value).compressed
    except ValueError:
        return None


def client_ip_for_throttle(request):
    remote = _ip(request.META.get("REMOTE_ADDR", ""))
    mode = getattr(settings, "EKAKO_CLIENT_IP_SOURCE", "remote")

    if mode == "cloudflare":
        # La vérification de confiance est du ressort du reverse proxy Render :
        # à activer uniquement si l'origine n'accepte pas de trafic direct
        # contournant le proxy et si CF-Connecting-IP est réécrit par celui-ci.
        cf_ip = _ip(request.META.get("HTTP_CF_CONNECTING_IP", ""))
        if cf_ip is not None:
            return cf_ip

    return remote or "unknown"
