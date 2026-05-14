import json, random
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Order
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from orders.models import Order, OrderItem, OrderStatusLog
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
    payload = json.loads(request.body.decode("utf-8") or "{}")
    

    customer = payload.get("customer") or {}
    items = payload.get("items") or []

    for k in ("name", "phone", "city", "quarter", "address"):
        if not customer.get(k):
            return JsonResponse({"ok": False, "error": f"Champ manquant: customer.{k}"}, status=400)

    if not items:
        return JsonResponse({"ok": False, "error": "Panier vide."}, status=400)

    pricing_mode = "reseller" if is_reseller(request.user) else "retail"

    if pricing_mode == "reseller":
        agg = {}
        for it in items:
            sku = (it.get("sku") or "").strip()
            qty = int(it.get("qty") or 0)
            if sku:
                agg[sku] = agg.get(sku, 0) + qty

        from catalog.models import Product
        for sku, total_qty in agg.items():
            try:
                p = Product.objects.get(sku=sku)
            except Product.DoesNotExist:
                return JsonResponse({"ok": False, "error": f"SKU inconnu: {sku}"}, status=400)

            moq = int(p.reseller_moq or 1)
            if total_qty < moq:
                return JsonResponse(
                    {"ok": False, "error": f"MOQ non atteint pour {sku}. Minimum: {moq}, Actuel: {total_qty}"},
                    status=400,
                )

    with transaction.atomic():
        subtotal = 0
        order_items = []

        for it in items:
            sku = (it.get("sku") or "").strip()

            try:
                size = str(it.get("size") or "").strip()
                qty = int(it.get("qty") or 0)
            except (TypeError, ValueError):
                return JsonResponse({"ok": False, "error": "Item invalide (option/qty)."}, status=400)


            if not sku or not size or qty <= 0:
                return JsonResponse({"ok": False, "error": "Item invalide (option/qty)."}, status=400)

            try:
                variant = (
                    Variant.objects
                    .select_for_update()
                    .select_related("product", "size")
                    .get(product__sku=sku, size__label=size)
                )
            except Variant.DoesNotExist:
                return JsonResponse(
                    {"ok": False, "error": f"Variante introuvable: {sku} option {size}"},
                    status=400
                )

            if variant.stock_qty < qty:
                return JsonResponse(
                    {"ok": False, "error": f"Stock insuffisant: {sku} option {size} dispo {variant.stock_qty}"},
                    status=400
                )

            product = variant.product

            if pricing_mode == "reseller":
                unit_price = int(product.reseller_price or 0)
            else:
                unit_price = int(product.retail_price or 0)

            line_total = unit_price * qty
            subtotal += line_total
            order_items.append((variant, product, unit_price, qty, line_total))

        shipping_fee = compute_shipping(
            customer.get("city", "Autre"),
            customer.get("quarter", "Autre")
        )
        total = subtotal + shipping_fee

        order = None
        for _ in range(10):
            order_no = gen_order_no()
            try:
                order = Order.objects.create(
                    order_no=order_no,
                    customer_name=customer["name"],
                    customer_phone=customer["phone"],
                    city=customer["city"],
                    quarter=customer["quarter"],
                    address=customer["address"],
                    pay_method=payload.get("pay_method", "MTN Mobile Money"),
                    shipping_fee=shipping_fee,
                    subtotal=subtotal,
                    total=total,
                    mode=pricing_mode,
                    user=request.user if request.user.is_authenticated else None,
                )
                break
            except IntegrityError:
                order = None
                continue

        if order is None:
            return JsonResponse(
                {"ok": False, "error": "Impossible de générer un numéro de commande unique. Réessaie."},
                status=500
            )

        for (variant, product, unit_price, qty, line_total) in order_items:
            OrderItem.objects.create(
                order=order,
                variant=variant,
                sku=product.sku,
                product_name=product.name,
                size_value=variant.size.label,
                unit_price=unit_price,
                qty=qty,
                line_total=line_total
            )
            variant.stock_qty -= qty
            variant.save(update_fields=["stock_qty"])

    return JsonResponse({"ok": True, "orderNo": order.order_no, "mode": pricing_mode})

def track_api(request, order_no: str):
    try:
        o = Order.objects.prefetch_related("items").get(order_no=order_no)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    return JsonResponse({
        "ok": True,
        "order": {
            "orderNo": o.order_no,
            "status": o.status,
            "createdAt": o.created_at.isoformat(),
            "customer": {
                "name": o.customer_name,
                "phone": o.customer_phone,
                "city": o.city,
                "quarter": o.quarter,
                "address": o.address,
            },
            "shipping": o.shipping_fee,
            "subtotal": o.subtotal,
            "total": o.total,
            "items": [
                {
                    "sku": it.sku,
                    "name": it.product_name,
                    "size": it.size_value,
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


@user_passes_test(can_view_orders)
@require_POST
def admin_update_status_api(request, order_no: str):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    new_status = (payload.get("status") or "").strip().lower()
    note = (payload.get("note") or "").strip()

    if new_status not in ALLOWED_STATUSES:
        return JsonResponse({"ok": False, "error": "Statut invalide."}, status=400)

    try:
        o = Order.objects.select_related().get(order_no=order_no)
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    old_status = (o.status or "").strip().lower()

    if new_status == old_status:
        return JsonResponse({"ok": True, "orderNo": o.order_no, "status": o.status})

    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        return JsonResponse(
            {"ok": False, "error": f"Transition interdite: {old_status} → {new_status}"},
            status=400,
        )

    should_restock = (new_status in {"cancelled", "failed"} and old_status in {"received", "preparing"})

    with transaction.atomic():
        if should_restock:
            for it in o.items.select_related("variant").select_for_update():
                v = it.variant
                v.stock_qty = (v.stock_qty or 0) + int(it.qty or 0)
                v.save(update_fields=["stock_qty"])

        o.status = new_status
        o.save(update_fields=["status"])

        OrderStatusLog.objects.create(
            order=o,
            old_status=old_status,
            new_status=new_status,
            changed_by=request.user if request.user.is_authenticated else None,
            note=note
        )

    return JsonResponse({"ok": True, "orderNo": o.order_no, "status": o.status})


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
                "qty": it.qty,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            } for it in o.items.all()
        ],
    }
})

ALLOWED_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed"}

@user_passes_test(can_view_orders)
def admin_update_payment_status_api(request, order_no: str):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = {}

    new_status = (payload.get("payment_status") or "").strip().lower()
    payment_ref = (payload.get("payment_ref") or "").strip()

    if new_status not in {"unpaid", "pending", "paid", "failed"}:
        return JsonResponse({"ok": False, "error": "Statut de paiement invalide."}, status=400)

    try:
        o = Order.objects.get(order_no__iexact=(order_no or "").strip())
    except Order.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Commande introuvable."}, status=404)

    o.payment_state = new_status
    o.payment_reference = payment_ref

    if new_status == "paid":
        o.paid_at = timezone.now()
    else:
        o.paid_at = None

    o.save()

    return JsonResponse({
        "ok": True,
        "orderNo": o.order_no,
        "payment_status": o.payment_state,
        "payment_ref": o.payment_reference,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
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
