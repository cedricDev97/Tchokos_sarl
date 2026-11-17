"""Limitation des recherches répétées dans le suivi de commande eKAKO.

Compteurs SQL partagés avec l'infrastructure existante et clés HMAC séparées
de celles de la connexion. Aucune commande, IP ou numéro de téléphone en clair.
"""
import hashlib
import hmac
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import LoginAttemptCounter

WINDOW = timedelta(minutes=15)
PAIR_LIMIT = 5
IP_LIMIT = 20


def _keys(request, order_no):
    ip = str(request.META.get("REMOTE_ADDR", "") or "unknown")
    order = str(order_no).strip().casefold()
    secret = settings.SECRET_KEY.encode("utf-8")

    def digest(value):
        return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()

    return (digest("order-track-pair:" + ip + ":" + order),
            digest("order-track-ip:" + ip))


def tracking_retry_after(request, order_no):
    now = timezone.now()
    pair, ip = _keys(request, order_no)
    intervals = []
    for key, limit in ((pair, PAIR_LIMIT), (ip, IP_LIMIT)):
        row = LoginAttemptCounter.objects.filter(key=key).first()
        if row and row.expires_at > now and row.failures >= limit:
            intervals.append(max(1, math.ceil((row.expires_at - now).total_seconds())))
    return max(intervals, default=0)


def record_failed_tracking(request, order_no):
    now = timezone.now()
    for key in _keys(request, order_no):
        with transaction.atomic():
            row, _ = LoginAttemptCounter.objects.get_or_create(
                key=key, defaults={"expires_at": now + WINDOW},
            )
            row = LoginAttemptCounter.objects.select_for_update().get(key=key)
            if row.expires_at <= now:
                row.failures = 0
                row.expires_at = now + WINDOW
                row.save(update_fields=["failures", "expires_at"])
            LoginAttemptCounter.objects.filter(key=key).update(
                failures=F("failures") + 1,
            )


def clear_successful_tracking(request, order_no):
    pair, _ = _keys(request, order_no)
    LoginAttemptCounter.objects.filter(key=pair).delete()
