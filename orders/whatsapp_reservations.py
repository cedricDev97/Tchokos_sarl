"""Expiration idempotente des reservations WhatsApp non confirmees."""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import Variant
from orders.models import Order, OrderStatusLog
from sourcing.models import ProcurementLine


def expire_whatsapp_reservations(limit=200):
    now = timezone.now()
    candidates = list(
        Order.objects.filter(
            checkout_channel="whatsapp",
            reservation_expires_at__lte=now,
            status="received",
            payment_state__in=("unpaid", "pending"),
        ).order_by("reservation_expires_at").values_list("pk", flat=True)[:limit]
    )
    expired = 0
    for pk in candidates:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk).first()
            if (order is None or order.checkout_channel != "whatsapp"
                    or order.status != "received" or order.payment_state not in {"unpaid", "pending"}
                    or not order.reservation_expires_at
                    or order.reservation_expires_at > timezone.now()):
                continue
            # Aucune restitution automatique si le commerçant a déjà réservé/collecté.
            if ProcurementLine.objects.filter(
                order_item__order=order, status__in=("confirmed", "collected"),
            ).exists():
                continue
            updated = Order.objects.filter(pk=pk, status="received").update(
                status="cancelled", reservation_expires_at=None,
            )
            if not updated:
                continue
            for item in order.items.all():
                Variant.objects.filter(pk=item.variant_id).update(stock_qty=F("stock_qty") + item.qty)
            ProcurementLine.objects.filter(order_item__order=order).update(status="cancelled")
            OrderStatusLog.objects.create(
                order=order, old_status="received", new_status="cancelled",
                note="Réservation WhatsApp expirée sans confirmation de paiement.",
            )
            expired += 1
    return expired
