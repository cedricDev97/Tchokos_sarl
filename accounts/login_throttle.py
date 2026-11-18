"""Limitation des mots de passe erronés pour la connexion eKAKO.

Ne pas se fier aux en-têtes X-Forwarded-For fournis par le client.
Le reverse proxy doit communiquer l'adresse du client via REMOTE_ADDR
ou un mécanisme de proxy explicitement configuré et de confiance.
"""
import hashlib
import hmac
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import LoginAttemptCounter

WINDOW = timedelta(minutes=15)
PAIR_LIMIT = 5
IP_LIMIT = 20


def _keys(request, username):
    from config.client_ip import client_ip_for_throttle
    raw_ip = client_ip_for_throttle(request)
    normalized_user = str(username).strip().casefold()
    secret = settings.SECRET_KEY.encode("utf-8")

    def digest(part):
        return hmac.new(secret, part.encode("utf-8"), hashlib.sha256).hexdigest()

    return (digest("pair:" + raw_ip + ":" + normalized_user),
            digest("ip:" + raw_ip))


def _counter(key, now):
    with transaction.atomic():
        counter, _ = LoginAttemptCounter.objects.get_or_create(
            key=key, defaults={"expires_at": now + WINDOW}
        )
        # select_for_update est effectif sous PostgreSQL, base de production.
        counter = LoginAttemptCounter.objects.select_for_update().get(key=key)
        if counter.expires_at <= now:
            counter.failures = 0
            counter.expires_at = now + WINDOW
            counter.save(update_fields=["failures", "expires_at"])
        return counter


def login_retry_after(request, username):
    """Renvoie le nombre de secondes à attendre, ou zéro."""
    now = timezone.now()
    pair, ip = _keys(request, username)
    delays = []
    for key, limit in ((pair, PAIR_LIMIT), (ip, IP_LIMIT)):
        row = LoginAttemptCounter.objects.filter(key=key).first()
        if row and row.expires_at > now and row.failures >= limit:
            delays.append(max(1, math.ceil((row.expires_at - now).total_seconds())))
    return max(delays, default=0)


def record_failed_login(request, username):
    """Augmente deux compteurs ; la base garantit les mises à jour atomiques."""
    now = timezone.now()
    for key in _keys(request, username):
        _counter(key, now)
        LoginAttemptCounter.objects.filter(key=key).update(failures=F("failures") + 1)


def clear_successful_login(request, username):
    """Réinitialise le compteur lié à cet identifiant et cette IP."""
    pair, _ = _keys(request, username)
    LoginAttemptCounter.objects.filter(key=pair).delete()
