import json, random
import hashlib
import re
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Order
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from orders.models import Order, OrderItem, OrderStatusLog, PaymentStatusLog, CheckoutAttempt, CODCollection
from django.utils import timezone
#from django.views.decorators.csrf import csrf_exempt
from catalog.models import Variant, Product
from .models import Order, OrderItem
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
import uuid

from django.contrib.auth.decorators import user_passes_test
from accounts.permissions import (
    can_manage_orders,
    can_manage_payments,
    can_manage_inventory,
    can_manage_resellers,
    can_view_orders
)

SHIPPING = {
    "Douala": {"base": 1500, "quarters": {"Akwa":500, "Bonamoussadi":700, "Deido":600, "Logpom":900, "PK14":1200, "Autre":1400}},
    "Yaounde":{"base": 2500, "quarters": {"Bastos":900, "Mvan":700, "Nlongkak":800, "Emana":900, "Autre":1200}},
    "Kribi":  {"base": 2000, "quarters": {"Centre":700, "Beach":900, "Autre":1100}},
    "Bafoussam": {"base": 3000, "quarters": {"Centre":800, "Autre":1200}},
    "Autre": {"base": 4000, "quarters": {"Autre":1000}},
}

def compute_shipping(city: str, quarter: str) -> int:
    conf = SHIPPING.get(city) or SHIPPING["Autre"]
    base = int(conf.get("base", 0))
    qmap = conf.get("quarters") or {"Autre": 0}
    add = int(qmap.get(quarter, qmap.get("Autre", 0)))
    return max(0, base + add)



def is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)

def is_reseller(user):
    return user.is_authenticated and user.groups.filter(name="reseller").exists()

def gen_order_no():
    return "TK" + uuid.uuid4().hex[:8].upper()

def is_reseller(user):
    return user.is_authenticated and user.groups.filter(name="reseller").exists()


from django.db import transaction, IntegrityError
import json

@require_POST
def checkout_api(request):
    """Créer une commande et décrémenter chaque variante UNE fois, atomiquement."""
    from django.db import OperationalError
    from django.db.models import F

    class CheckoutRejected(Exception):
        pass

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Requête JSON invalide."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)

    customer = payload.get("customer")
    items = payload.get("items")
    if not isinstance(customer, dict):
        return JsonResponse({"ok": False, "error": "Client invalide."}, status=400)
    if not isinstance(items, list) or not items or len(items) > 50:
        return JsonResponse({"ok": False, "error": "Le panier doit contenir entre 1 et 50 lignes."}, status=400)

    limits = {"name": 120, "phone": 30, "city": 80, "quarter": 120, "address": 255}
    clean_customer = {}
    for field, maximum in limits.items():
        value = customer.get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            return JsonResponse({"ok": False, "error": f"Champ client invalide : {field}."}, status=400)
        clean_customer[field] = value.strip()

    # Même SKU + même taille : toutes les lignes comptent comme une seule demande.
    quantities = {}
    total_quantity = 0
    for it in items:
        if not isinstance(it, dict):
            return JsonResponse({"ok": False, "error": "Article invalide."}, status=400)
        sku = it.get("sku")
        size = it.get("size")
        raw_qty = it.get("qty")
        if not isinstance(sku, str) or not isinstance(size, str):
            return JsonResponse({"ok": False, "error": "SKU ou option invalide."}, status=400)
        sku, size = sku.strip().upper(), size.strip()
        if not sku or not size or len(sku) > 40 or len(size) > 50:
            return JsonResponse({"ok": False, "error": "SKU ou option invalide."}, status=400)
        if isinstance(raw_qty, bool) or not isinstance(raw_qty, int) or raw_qty <= 0 or raw_qty > 500:
            return JsonResponse({"ok": False, "error": "Quantité invalide (1 à 500)."}, status=400)
        key = (sku, size)
        quantities[key] = quantities.get(key, 0) + raw_qty
        total_quantity += raw_qty
        if quantities[key] > 500 or total_quantity > 2000:
            return JsonResponse({"ok": False, "error": "Quantité demandée trop élevée."}, status=400)

    pay_method = payload.get("pay_method", "MTN Mobile Money")
    if not isinstance(pay_method, str) or not pay_method.strip() or len(pay_method.strip()) > 80:
        return JsonResponse({"ok": False, "error": "Moyen de paiement invalide."}, status=400)

    if pay_method.strip() not in {"MTN Mobile Money", "Orange Money", "Paiement a la livraison (optionnel)"}:
        return JsonResponse({"ok": False, "error": "Moyen de paiement non pris en charge."}, status=400)

    pricing_mode = "reseller" if is_reseller(request.user) else "retail"

    # Le navigateur conserve cette clé en cas de timeout/rejeu.
    # En production, une clé explicite est obligatoire.
    checkout_key = (request.headers.get("Idempotency-Key") or "").strip()
    if not checkout_key and getattr(settings, "IS_PRODUCTION", False):
        return JsonResponse({"ok": False, "error": "Clé de commande manquante."}, status=400)
    if not checkout_key:
        checkout_key = uuid.uuid4().hex  # compatibilité avec anciens tests / développement
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", checkout_key):
        return JsonResponse({"ok": False, "error": "Clé de commande invalide."}, status=400)

    canonical_request = {
        "customer": clean_customer,
        "items": sorted([[sku, size, qty] for (sku, size), qty in quantities.items()]),
        "pay_method": pay_method.strip(),
        "mode": pricing_mode,
        "user_id": request.user.pk if request.user.is_authenticated else None,
    }
    request_hash = hashlib.sha256(
        json.dumps(canonical_request, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        with transaction.atomic():
            # La contrainte UNIQUE fait attendre les tentatives concurrentes
            # sur PostgreSQL, AVANT toute modification de disponibilité.
            try:
                with transaction.atomic():
                    checkout_attempt = CheckoutAttempt.objects.create(
                        key=checkout_key, request_hash=request_hash,
                    )
            except IntegrityError:
                previous = CheckoutAttempt.objects.select_related("order").get(key=checkout_key)
                if previous.request_hash != request_hash:
                    return JsonResponse({
                        "ok": False, "error": "Cette clé a déjà été utilisée pour une autre commande."
                    }, status=409)
                if not previous.order_id:
                    return JsonResponse({
                        "ok": False, "error": "Commande en cours de confirmation. Réessaie."
                    }, status=503)
                return JsonResponse({
                    "ok": True, "orderNo": previous.order.order_no,
                    "mode": previous.order.mode, "idempotent": True,
                })

            order_lines = []
            sku_totals = {}
            subtotal = 0

            for (sku, size), qty in quantities.items():
                try:
                    variant = (Variant.objects.select_related("product", "size")
                               .get(product__sku=sku, size__label=size))
                except Variant.DoesNotExist:
                    raise CheckoutRejected(f"Produit ou option introuvable : {sku}, {size}.")

                product = variant.product
                if not product.is_active:
                    raise CheckoutRejected(f"Produit indisponible : {sku}.")
                if variant.stock_qty < qty:
                    raise CheckoutRejected(f"Stock insuffisant : {sku}, {size} (disponible : {variant.stock_qty}).")

                sku_totals[sku] = sku_totals.get(sku, 0) + qty
                unit_price = int(product.reseller_price if pricing_mode == "reseller" else product.retail_price)
                line_total = unit_price * qty
                subtotal += line_total
                order_lines.append((variant, product, qty, unit_price, line_total))

            if pricing_mode == "reseller":
                for variant, product, qty, unit_price, line_total in order_lines:
                    minimum = int(product.reseller_moq or 1)
                    if sku_totals[product.sku] < minimum:
                        raise CheckoutRejected(
                            f"MOQ non atteint pour {product.sku} : minimum {minimum}, demandé {sku_totals[product.sku]}."
                        )

            # Mise à jour conditionnelle exécutée par la BD : pas de stock négatif.
            # L'ordre croissant des PK limite les deadlocks en cas de paniers
            # contenant plusieurs variantes demandées en ordre inverse.
            for variant, product, qty, unit_price, line_total in sorted(
                order_lines, key=lambda row: row[0].pk
            ):
                changed = Variant.objects.filter(
                    pk=variant.pk, stock_qty__gte=qty
                ).update(stock_qty=F("stock_qty") - qty)
                if changed != 1:
                    raise CheckoutRejected(
                        f"Stock modifié entre-temps pour {product.sku}, {variant.size.label}. Réessaie."
                    )

            shipping_fee = compute_shipping(clean_customer["city"], clean_customer["quarter"])
            order = None
            for _ in range(5):
                try:
                    # Savepoint : une collision de numéro ne casse pas la transaction.
                    with transaction.atomic():
                        order = Order.objects.create(
                            order_no=gen_order_no(),
                            customer_name=clean_customer["name"],
                            customer_phone=clean_customer["phone"],
                            city=clean_customer["city"],
                            quarter=clean_customer["quarter"],
                            address=clean_customer["address"],
                            pay_method=pay_method.strip(),
                            shipping_fee=shipping_fee,
                            subtotal=subtotal,
                            total=subtotal + shipping_fee,
                            mode=pricing_mode,
                            user=request.user if request.user.is_authenticated else None,
                        )
                    break
                except IntegrityError:
                    continue
            if order is None:
                raise CheckoutRejected("Numéro de commande indisponible. Réessaie.")

            created_items = OrderItem.objects.bulk_create([
                OrderItem(
                    order=order, variant=variant, sku=product.sku,
                    product_name=product.name, size_value=variant.size.label,
                    color_name=(product.color_name or "").strip(),
                    unit_price=unit_price, qty=qty, line_total=line_total,
                )
                for variant, product, qty, unit_price, line_total in order_lines
            ])

            # EKAKO_MODELE_B_V1 : une fiche de collecte par article et une livraison
            # par commande. Aucun appel externe ni paiement fournisseur effectué ici.
            from sourcing.models import SupplierOffer, ProcurementLine, DeliveryTask
            offers = {
                offer.product_id: offer
                for offer in SupplierOffer.objects.select_related("supplier").filter(
                    product_id__in=[product.pk for _, product, _, _, _ in order_lines]
                )
            }
            requests = []
            for created_item, (variant, product, qty, unit_price, line_total) in zip(created_items, order_lines):
                offer = offers.get(product.pk)
                if offer and offer.availability_state == "unavailable":
                    request_status = "unavailable"
                elif offer and offer.supplier.status == "active":
                    request_status = "to_confirm"
                else:
                    request_status = "unassigned"
                requests.append(ProcurementLine(
                    order_item=created_item,
                    supplier=offer.supplier if offer else None,
                    unit_cost=offer.purchase_price if offer else None,
                    status=request_status,
                ))
            ProcurementLine.objects.bulk_create(requests)
            DeliveryTask.objects.create(order=order)
            checkout_attempt.order = order
            checkout_attempt.save(update_fields=["order"])
    except CheckoutRejected as exc:
        # L'atomicité annule aussi toute décrémentation déjà effectuée.
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except OperationalError:
        return JsonResponse({"ok": False, "error": "Stock momentanément occupé. Réessaie."}, status=503)

    return JsonResponse({"ok": True, "orderNo": order.order_no, "mode": pricing_mode})

# EKAKO_COMMANDES_SECURITE_V1 : second facteur de vérification du suivi client.
@require_POST
def track_api(request, order_no: str):
    import hmac

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)

    supplied = "".join(ch for ch in str(payload.get("phone") or "") if ch.isascii() and ch.isdigit())
    if len(supplied) < 8:
        return JsonResponse({"ok": False, "error": "Indique le téléphone associé à ta commande."}, status=400)

    try:
        o = Order.objects.prefetch_related("items").get(order_no=order_no)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable pour ces informations."}, status=404)

    expected = "".join(ch for ch in str(o.customer_phone or "") if ch.isascii() and ch.isdigit())
    if not hmac.compare_digest(supplied, expected):
        return JsonResponse({"ok": False, "error": "Commande introuvable pour ces informations."}, status=404)

    return JsonResponse({
        "ok": True,
        "order": {
            "orderNo": o.order_no,
            "status": o.status,
            "createdAt": o.created_at.isoformat(),
            "customer": {
                "name": o.customer_name,
                "city": o.city,
                "quarter": o.quarter,
            },
            "shipping": o.shipping_fee,
            "subtotal": o.subtotal,
            "total": o.total,
            "items": [
                {
                    "sku": it.sku,
                    "name": it.product_name,
                    "size": it.size_value,
                    "color": it.color_name or (it.variant.product.color_name if it.variant_id else ""),
                    "qty": it.qty,
                    "unit": it.unit_price,
                    "line_total": it.line_total,
                }
                for it in o.items.all()
            ],
        }
    })


@user_passes_test(can_manage_orders)
def admin_stats_api(request):
    days_raw = request.GET.get("days", "7")  # "ALL" ou "7" ou "30"
    qs = Order.objects.all()

    if days_raw != "ALL":
        days = int(days_raw)
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)

    revenue = qs.aggregate(s=Sum("total"))["s"] or 0
    orders_count = qs.count()
    avg = int(revenue / orders_count) if orders_count else 0

    return JsonResponse({
        "ok": True,
        "range": days_raw,
        "revenue": revenue,
        "orders": orders_count,
        "avg_order": avg,
    })


@user_passes_test(can_view_orders)
def admin_orders_api(request):
    # derniers 50
    qs = Order.objects.order_by("-created_at")[:50]
    return JsonResponse({
        "ok": True,
        "results": [
            {
                "orderNo": o.order_no,
                "status": o.status,
                "createdAt": o.created_at.isoformat(),
                "name": o.customer_name,
                "phone": o.customer_phone,
                "city": o.city,
                "quarter": o.quarter,
                "total": o.total,
                "pay_method": o.pay_method,
                "payment_status": getattr(o, "payment_state", "unpaid"),
                "payment_ref": getattr(o, "payment_reference", ""),
            }
            for o in qs
        ]
    })

ALLOWED_STATUSES = {"received", "preparing", "shipped", "delivered", "cancelled", "failed"}

ALLOWED_TRANSITIONS = {
    "received": {"preparing", "cancelled", "failed"},
    "preparing": {"shipped", "cancelled", "failed"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
    "failed": set(),
}


def is_cod_payment_method(method):
    """Uniquement le mode de paiement à la livraison connu de notre checkout."""
    value = str(method or "").strip().casefold()
    return value in {"paiement a la livraison (optionnel)", "paiement à la livraison (optionnel)"}


def digital_payment_confirmed(order):
    return is_cod_payment_method(order.pay_method) or order.payment_state == "paid"


def restock_order(order: Order):
    """
    Remet le stock des variantes liées à une commande.
    À appeler uniquement si la commande n'a pas été expédiée.
    """
    items = order.items.select_related("variant").all()
    for it in items:
        v = it.variant
        # on remet le stock
        v.stock_qty = (v.stock_qty or 0) + int(it.qty or 0)
        v.save(update_fields=["stock_qty"])


@user_passes_test(can_manage_orders)
@require_POST
def admin_update_status_api(request, order_no: str):
    """Transition atomique ; le stock n'est restitué qu'une seule fois."""
    from django.db import OperationalError
    from django.db.models import F

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "JSON invalide."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)
    new_status = str(payload.get("status") or "").strip().lower()
    note = str(payload.get("note") or "").strip()[:255]
    if new_status not in ALLOWED_STATUSES:
        return JsonResponse({"ok": False, "error": "Statut invalide."}, status=400)

    try:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(order_no=order_no)
            except Order.DoesNotExist:
                return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

            old_status = (order.status or "").strip().lower()
            if old_status == new_status:
                return JsonResponse({"ok": True, "orderNo": order.order_no, "status": order.status})
            if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
                return JsonResponse({"ok": False,
                                     "error": f"Transition interdite : {old_status} vers {new_status}."}, status=400)

            # Une commande payée ne peut pas être annulée sans procédure de remboursement.
            # Une réservation fournisseur confirmée/collectée nécessite une résolution préalable.
            if new_status in {"cancelled", "failed"}:
                from sourcing.models import ProcurementLine
                if order.payment_state == "paid" or CODCollection.objects.filter(order=order).exists():
                    return JsonResponse({
                        "ok": False, "error": "Encaissement enregistré : annulation bloquée, rapprochement/remboursement requis."
                    }, status=409)
                if ProcurementLine.objects.filter(order_item__order=order, status__in={"confirmed", "collected"}).exists():
                    return JsonResponse({
                        "ok": False, "error": "Libère la réservation fournisseur ou traite le retour avant d'annuler."
                    }, status=409)

            # Paiement à la livraison : préparation / expédition permises avant encaissement.
            # Mobile Money : ne jamais préparer/expédier une commande non confirmée.
            if new_status in {"preparing", "shipped", "delivered"} and not digital_payment_confirmed(order):
                return JsonResponse({
                    "ok": False,
                    "error": "Paiement Mobile Money non confirmé : préparation/expédition bloquée."
                }, status=409)

            # Modèle B : commandes créées depuis le checkout (fiche de livraison présente).
            # Les anciennes commandes sans sourcing restent consultables et gérables.
            if new_status in {"preparing", "shipped", "delivered"}:
                from sourcing.models import DeliveryTask, ProcurementLine
                delivery = DeliveryTask.objects.select_for_update().filter(order=order).first()
                if delivery is not None:
                    sourcing_rows = ProcurementLine.objects.select_for_update().filter(order_item__order=order)
                    if sourcing_rows.count() != order.items.count():
                        return JsonResponse({
                            "ok": False, "error": "Approvisionnement incomplet : lignes manquantes."
                        }, status=409)
                    if new_status == "preparing" and sourcing_rows.exclude(
                        status__in={"confirmed", "collected"}
                    ).exists():
                        return JsonResponse({
                            "ok": False, "error": "Le commerçant doit confirmer tous les articles."
                        }, status=409)
                    if new_status == "shipped":
                        if sourcing_rows.exclude(status="collected").exists():
                            return JsonResponse({
                                "ok": False, "error": "Expédition bloquée : tous les articles ne sont pas collectés."
                            }, status=409)
                        if delivery.status not in {"assigned", "out_for_delivery"} or not delivery.courier_name.strip():
                            return JsonResponse({
                                "ok": False, "error": "Affecte un livreur avant l'expédition."
                            }, status=409)
                    if new_status == "delivered" and delivery.status != "delivered":
                        return JsonResponse({
                            "ok": False, "error": "Confirme la remise dans la fiche de livraison."
                        }, status=409)
                    if new_status == "delivered" and is_cod_payment_method(order.pay_method):
                        receipt = CODCollection.objects.select_for_update().filter(order=order).first()
                        if receipt is None or receipt.amount != order.total:
                            return JsonResponse({
                                "ok": False, "error": "Déclare l'encaissement COD complet avant de marquer Livrée."
                            }, status=409)

            changed = Order.objects.filter(pk=order.pk, status=old_status).update(status=new_status)
            if changed != 1:
                return JsonResponse({"ok": False, "error": "Statut modifié entre-temps. Actualise."}, status=409)

            if new_status in {"cancelled", "failed"} and old_status in {"received", "preparing"}:
                for item in order.items.all():
                    Variant.objects.filter(pk=item.variant_id).update(
                        stock_qty=F("stock_qty") + item.qty
                    )

            if new_status in {"cancelled", "failed"}:
                from sourcing.models import ProcurementLine
                ProcurementLine.objects.filter(order_item__order=order).exclude(
                    status="collected"
                ).update(status="cancelled")

            OrderStatusLog.objects.create(
                order=order, old_status=old_status, new_status=new_status,
                changed_by=request.user if request.user.is_authenticated else None,
                note=note,
            )
    except OperationalError:
        return JsonResponse({"ok": False, "error": "Commande momentanément occupée. Réessaie."}, status=503)

    return JsonResponse({"ok": True, "orderNo": order.order_no, "status": new_status})

@user_passes_test(can_manage_orders)
def admin_analytics_api(request):
    days_raw = request.GET.get("days", "7")  # ALL/7/30
    qs_orders = Order.objects.all()
    if days_raw != "ALL":
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=int(days_raw))
        qs_orders = qs_orders.filter(created_at__gte=since)

    order_ids = qs_orders.values_list("id", flat=True)

    # Top produits (quantité)
    top = (OrderItem.objects
           .filter(order_id__in=order_ids)
           .values("sku", "product_name")
           .annotate(qty=Sum("qty"))
           .order_by("-qty")[:8])

    # CA par zone
    zones = (qs_orders
             .values("city", "quarter")
             .annotate(revenue=Sum("total"))
             .order_by("-revenue")[:12])

    return JsonResponse({
        "ok": True,
        "top_products": list(top),
        "revenue_by_zone": list(zones),
    })

@user_passes_test(can_manage_inventory)
def admin_inventory_api(request):
    qs = (Variant.objects
          .select_related("product", "size")
          .order_by("product__sku", "size__label"))

    rows = {}
    for v in qs:
        sku = v.product.sku
        if sku not in rows:
            rows[sku] = {
                "sku": sku,
                "name": v.product.name,
                "sizes": {}
            }
        rows[sku]["sizes"][str(v.size.label)] = int(v.stock_qty)

    return JsonResponse({"ok": True, "results": list(rows.values())})

@user_passes_test(can_manage_inventory)
@require_POST
def admin_adjust_stock_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON invalide."}, status=400)

    sku = str(payload.get("sku") or "").strip()
    size = str(payload.get("size") or "").strip()

    try:
        delta = int(payload.get("delta") or 0)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Delta invalide."}, status=400)

    if not sku or not size:
        return JsonResponse({"ok": False, "error": "SKU ou option manquante."}, status=400)

    if delta not in (-1, 1, 5, -5):
        return JsonResponse({"ok": False, "error": "Delta invalide."}, status=400)

    with transaction.atomic():
        try:
            v = (
                Variant.objects
                .select_for_update()
                .select_related("product", "size")
                .get(product__sku=sku, size__label=size)
            )
        except Variant.DoesNotExist:
            return JsonResponse(
                {"ok": False, "error": f"Variante introuvable: {sku} option {size}"},
                status=404
            )

        new_qty = int(v.stock_qty or 0) + delta
        if new_qty < 0:
            return JsonResponse({"ok": False, "error": "Stock ne peut pas être négatif."}, status=400)

        v.stock_qty = new_qty
        v.save(update_fields=["stock_qty"])

    return JsonResponse({
        "ok": True,
        "sku": sku,
        "size": size,
        "stock_qty": new_qty
    })


'''def get_role(user):
    if user.is_superuser or user.is_staff or user.groups.filter(name__in=["admin", "Admin"]).exists():
        return "admin"
    if user.groups.filter(name="reseller").exists():
        return "reseller"
    return "visitor"

@login_required
def me_api(request):
    return JsonResponse({
        "ok": True,
        "authenticated": True,
        "username": request.user.username,
        "role": get_role(request.user),
    })'''

@require_POST
def login_api(request):
    payload = json.loads(request.body.decode("utf-8"))
    username = payload.get("username", "")
    password = payload.get("password", "")

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"ok": False, "error": "Identifiants invalides."}, status=400)

    login(request, user)
    return JsonResponse({"ok": True})

@require_POST
def logout_api(request):
    logout(request)
    return JsonResponse({"ok": True})

@user_passes_test(can_view_orders)
def admin_order_timeline_api(request, order_no: str):
    try:
        o = Order.objects.get(order_no=order_no)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    logs = o.status_logs.select_related("changed_by").all()[:100]
    return JsonResponse({
        "ok": True,
        "orderNo": o.order_no,
        "logs": [
            {
                "at": l.created_at.isoformat(),
                "old": l.old_status,
                "new": l.new_status,
                "by": (l.changed_by.username if l.changed_by else None),
                "note": l.note,
            } for l in logs
        ]
    })

@user_passes_test(can_view_orders)
def admin_order_detail_api(request, order_no: str):
    try:
        o = Order.objects.prefetch_related("items").get(order_no=order_no)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    return JsonResponse({
    "ok": True,
    "order": {
        "orderNo": o.order_no,
        "status": o.status,
        "createdAt": o.created_at.isoformat() if getattr(o, "created_at", None) else None,
        "name": o.customer_name,
        "phone": o.customer_phone,
        "city": o.city,
        "quarter": o.quarter,
        "address": o.address,
        "pay_method": getattr(o, "pay_method", ""),
        "payment_status": getattr(o, "payment_state", "unpaid"),
        "payment_ref": getattr(o, "payment_reference", ""),
        "paid_at": o.paid_at.isoformat() if getattr(o, "paid_at", None) else None,
        "shipping": int(getattr(o, "shipping_fee", 0) or 0),
        "subtotal": int(getattr(o, "subtotal", 0) or 0),
        "total": int(getattr(o, "total", 0) or 0),
        "mode": getattr(o, "mode", ""),
        "items": [
            {
                "sku": it.sku,
                "name": it.product_name,
                "size": it.size_value,
                    "color": it.color_name or (it.variant.product.color_name if it.variant_id else ""),
                "qty": it.qty,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            } for it in o.items.all()
        ],
    }
})



@user_passes_test(can_manage_orders)
@require_POST
def admin_cod_collect_api(request, order_no: str):
    """Déclaration manuelle COD, traçable et idempotente ; aucune monnaie transmise."""
    from django.db import OperationalError, IntegrityError
    from sourcing.models import DeliveryTask

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "JSON invalide."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)

    amount = payload.get("amount")
    raw_reference = payload.get("reference")
    note = payload.get("note", "")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        return JsonResponse({"ok": False, "error": "Montant COD invalide."}, status=400)
    if not isinstance(raw_reference, str):
        return JsonResponse({"ok": False, "error": "Référence COD invalide."}, status=400)
    reference = raw_reference.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{7,79}", reference):
        return JsonResponse({"ok": False, "error": "Référence COD invalide (8-80 caractères)."}, status=400)
    if not isinstance(note, str) or len(note.strip()) > 255:
        return JsonResponse({"ok": False, "error": "Note invalide."}, status=400)

    try:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(order_no__iexact=order_no.strip())
            except Order.DoesNotExist:
                return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

            if not is_cod_payment_method(order.pay_method):
                return JsonResponse({"ok": False, "error": "Commande non COD."}, status=409)
            if order.status not in {"shipped", "delivered"} or order.payment_state == "paid":
                return JsonResponse({"ok": False, "error": "Encaissement COD non autorisé à cette étape."}, status=409)
            if amount != order.total:
                return JsonResponse({"ok": False, "error": "Le montant doit correspondre au total de la commande."}, status=400)

            delivery = DeliveryTask.objects.select_for_update().filter(order=order).first()
            if (delivery is None or
                    delivery.status not in {"assigned", "out_for_delivery", "delivered"} or
                    not delivery.courier_name.strip()):
                return JsonResponse({"ok": False, "error": "Livreur non affecté ou livraison absente."}, status=409)

            existing = CODCollection.objects.filter(order=order).first()
            if existing:
                if (existing.reference, existing.amount, existing.courier_name) == (
                    reference, amount, delivery.courier_name.strip()
                ):
                    return JsonResponse({"ok": True, "orderNo": order.order_no, "reference": reference,
                                         "amount": amount, "idempotent": True})
                return JsonResponse({"ok": False, "error": "Un encaissement différent a déjà été déclaré."}, status=409)

            try:
                with transaction.atomic():
                    CODCollection.objects.create(
                        order=order, amount=amount, reference=reference,
                        courier_name=delivery.courier_name.strip(),
                        note=note.strip(), recorded_by=request.user,
                    )
            except IntegrityError:
                return JsonResponse({"ok": False, "error": "Référence COD déjà utilisée."}, status=409)
    except OperationalError:
        return JsonResponse({"ok": False, "error": "Encaissement momentanément occupé. Réessaie."}, status=503)

    return JsonResponse({"ok": True, "orderNo": order.order_no,
                         "reference": reference, "amount": amount})

ALLOWED_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed"}

@user_passes_test(can_manage_payments)
@require_POST
def admin_update_payment_status_api(request, order_no: str):
    """Validation manuelle auditée ; ne constitue PAS une vérification API MoMo."""
    from django.db import OperationalError

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "JSON invalide."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "Requête invalide."}, status=400)

    new_status = payload.get("payment_status")
    raw_reference = payload.get("payment_ref", "")
    note = payload.get("note", "")
    if not isinstance(new_status, str) or new_status.strip().lower() not in ALLOWED_PAYMENT_STATUSES:
        return JsonResponse({"ok": False, "error": "Statut de paiement invalide."}, status=400)
    if not isinstance(raw_reference, str) or len(raw_reference.strip()) > 120:
        return JsonResponse({"ok": False, "error": "Référence de paiement invalide."}, status=400)
    if not isinstance(note, str) or len(note.strip()) > 255:
        return JsonResponse({"ok": False, "error": "Note invalide."}, status=400)

    new_status = new_status.strip().lower()
    payment_ref = raw_reference.strip()
    verified = payload.get("verified") is True

    if new_status == "paid" and (not payment_ref or not verified):
        return JsonResponse({
            "ok": False,
            "error": "Pour marquer Payé : référence obligatoire et vérification manuelle explicite requise."
        }, status=400)

    try:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(order_no__iexact=(order_no or "").strip())
            except Order.DoesNotExist:
                return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

            old_state = order.payment_state
            old_reference = order.payment_reference or ""
            cod_receipt = None

            if old_state == "paid":
                if new_status == "paid" and old_reference == payment_ref:
                    return JsonResponse({
                        "ok": True, "orderNo": order.order_no,
                        "payment_status": old_state, "payment_ref": old_reference,
                        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                    })
                return JsonResponse({
                    "ok": False,
                    "error": "Paiement déjà confirmé : correction/remboursement à traiter via procédure dédiée."
                }, status=409)

            if new_status == "paid":
                if order.status in {"cancelled", "failed"}:
                    return JsonResponse({
                        "ok": False,
                        "error": "Commande clôturée : vérifier un éventuel paiement tardif avant rapprochement/remboursement."
                    }, status=409)
                if is_cod_payment_method(order.pay_method) and order.status != "delivered":
                    return JsonResponse({
                        "ok": False,
                        "error": "Paiement à la livraison : marquer Livrée avant de confirmer l'encaissement."
                    }, status=409)
                # Pour les NOUVELLES commandes COD : rapprochement obligatoire
                # avec la déclaration d'encaissement réalisée par le livreur.
                if is_cod_payment_method(order.pay_method):
                    from sourcing.models import DeliveryTask
                    if DeliveryTask.objects.filter(order=order).exists():
                        cod_receipt = CODCollection.objects.select_for_update().filter(order=order).first()
                        if cod_receipt is None or cod_receipt.amount != order.total:
                            return JsonResponse({
                                "ok": False, "error": "Déclaration COD absente ou montant incorrect."
                            }, status=409)
                        if cod_receipt.reference != payment_ref:
                            return JsonResponse({
                                "ok": False, "error": "Référence différente de la déclaration COD."
                            }, status=409)

                if Order.objects.filter(payment_state="paid", payment_reference__iexact=payment_ref).exclude(pk=order.pk).exists():
                    return JsonResponse({
                        "ok": False,
                        "error": "Référence déjà utilisée sur une autre commande payée."
                    }, status=409)

            # La transaction protège l'écriture et son journal.
            changed = Order.objects.filter(pk=order.pk, payment_state=old_state).update(
                payment_state=new_status,
                payment_reference=payment_ref,
                paid_at=timezone.now() if new_status == "paid" else None,
            )
            if changed != 1:
                return JsonResponse({"ok": False, "error": "Paiement modifié entre-temps. Actualise."}, status=409)
            PaymentStatusLog.objects.create(
                order=order, old_state=old_state, new_state=new_status,
                reference=payment_ref, note=note.strip(), changed_by=request.user,
            )
            if new_status == "paid" and cod_receipt is not None:
                CODCollection.objects.filter(pk=cod_receipt.pk, verified_at__isnull=True).update(
                    verified_at=timezone.now(), verified_by=request.user,
                )
            order.refresh_from_db(fields=["payment_state", "payment_reference", "paid_at"])
    except OperationalError:
        return JsonResponse({"ok": False, "error": "Paiement momentanément occupé. Réessaie."}, status=503)

    return JsonResponse({
        "ok": True,
        "orderNo": order.order_no,
        "payment_status": order.payment_state,
        "payment_ref": order.payment_reference,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    })

@login_required
@user_passes_test(is_reseller)
def reseller_my_orders_api(request):
    qs = (
        Order.objects
        .filter(user=request.user, mode="reseller")
        .prefetch_related("status_logs")
        .order_by("-created_at")[:100]
    )

    results = []
    for o in qs:
        last_log = o.status_logs.order_by("-created_at").first()

        if last_log:
            last_activity = {
                "at": last_log.created_at.isoformat() if last_log.created_at else None,
                "old": last_log.old_status,
                "new": last_log.new_status,
                "note": last_log.note or "",
            }
        else:
            last_activity = {
                "at": o.created_at.isoformat() if o.created_at else None,
                "old": None,
                "new": o.status,
                "note": "",
            }

        results.append({
            "orderNo": o.order_no,
            "createdAt": o.created_at.isoformat() if o.created_at else None,
            "status": o.status,
            "payment_status": getattr(o, "payment_state", "unpaid"),
            "payment_ref": getattr(o, "payment_reference", ""),
            "total": int(o.total or 0),
            "city": o.city,
            "quarter": o.quarter,
            "last_activity": last_activity,
        })

    return JsonResponse({
        "ok": True,
        "results": results
    })


@login_required
@user_passes_test(is_reseller)
def reseller_order_detail_api(request, order_no: str):
    try:
        o = (
            Order.objects
            .prefetch_related("items")
            .get(order_no=order_no, user=request.user, mode="reseller")
        )
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    return JsonResponse({
        "ok": True,
        "order": {
            "orderNo": o.order_no,
            "status": o.status,
            "createdAt": o.created_at.isoformat() if o.created_at else None,
            "name": o.customer_name,
            "phone": o.customer_phone,
            "city": o.city,
            "quarter": o.quarter,
            "address": o.address,
            "pay_method": getattr(o, "pay_method", ""),
            "payment_status": getattr(o, "payment_state", "unpaid"),
            "payment_ref": getattr(o, "payment_reference", ""),
            "paid_at": o.paid_at.isoformat() if getattr(o, "paid_at", None) else None,
            "shipping": int(getattr(o, "shipping_fee", 0) or 0),
            "subtotal": int(getattr(o, "subtotal", 0) or 0),
            "total": int(getattr(o, "total", 0) or 0),
            "mode": getattr(o, "mode", ""),
            "items": [
                {
                    "sku": it.sku,
                    "name": it.product_name,
                    "size": it.size_value,
                    "color": it.color_name or (it.variant.product.color_name if it.variant_id else ""),
                    "qty": it.qty,
                    "unit_price": it.unit_price,
                    "line_total": it.line_total,
                }
                for it in o.items.all()
            ],
        }
    })

@login_required
@user_passes_test(is_reseller)
def reseller_order_timeline_api(request, order_no: str):
    try:
        o = Order.objects.get(order_no=order_no, user=request.user, mode="reseller")
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    logs = o.status_logs.select_related("changed_by").all()[:100]

    return JsonResponse({
        "ok": True,
        "orderNo": o.order_no,
        "logs": [
            {
                "at": l.created_at.isoformat() if l.created_at else None,
                "old": l.old_status,
                "new": l.new_status,
                "by": (l.changed_by.username if l.changed_by else None),
                "note": l.note,
            }
            for l in logs
        ]
    })

@login_required
@user_passes_test(is_reseller)
def reseller_stats_api(request):
    qs = Order.objects.filter(user=request.user, mode="reseller")

    total_orders = qs.count()
    total_amount = sum(int(o.total or 0) for o in qs)
    delivered_orders = qs.filter(status="delivered").count()
    active_orders = qs.filter(status__in=["received", "preparing", "shipped"]).count()
    pending_payments = qs.filter(payment_state__in=["unpaid", "pending"]).count()

    avg_order = int(total_amount / total_orders) if total_orders else 0

    return JsonResponse({
        "ok": True,
        "stats": {
            "total_orders": total_orders,
            "total_amount": total_amount,
            "delivered_orders": delivered_orders,
            "active_orders": active_orders,
            "pending_payments": pending_payments,
            "avg_order": avg_order,
        }
    })

@login_required
@user_passes_test(is_reseller)
def reseller_top_products_api(request):
    rows = (
        OrderItem.objects
        .filter(order__user=request.user, order__mode="reseller")
        .values("sku", "product_name")
        .annotate(total_qty=Sum("qty"))
        .order_by("-total_qty", "product_name")[:5]
    )

    return JsonResponse({
        "ok": True,
        "results": [
            {
                "sku": r["sku"],
                "product_name": r["product_name"],
                "qty": int(r["total_qty"] or 0),
            }
            for r in rows
        ]
    })

# Create your views here.
