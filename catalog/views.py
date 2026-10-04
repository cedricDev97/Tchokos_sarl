import json

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import user_passes_test

from accounts.permissions import can_manage_inventory
from .models import Product, Size, Variant


def product_payload(request, p):
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "brand": p.brand,
        "category": p.category,
        "tag": p.tag,
        "description": p.description,
        "retail_price": int(p.retail_price or 0),
        "reseller_price": int(p.reseller_price or 0),
        "reseller_moq": int(p.reseller_moq or 1),
        "image_url": request.build_absolute_uri(p.image.url) if p.image else None,
        "variant_type": p.variant_type,
        "is_active": bool(p.is_active),
        "variants": [
            {
                "size": v.size.label,
                "stock_qty": int(v.stock_qty or 0),
            }
            for v in p.variants.select_related("size").all().order_by("size__label")
        ],
    }


def products_api(request):
    qs = (
        Product.objects
        .filter(is_active=True)
        .prefetch_related("variants__size")
        .order_by("name", "sku")
    )

    return JsonResponse({
        "results": [product_payload(request, p) for p in qs]
    })


@user_passes_test(can_manage_inventory)
@require_http_methods(["GET"])
def admin_products_api(request):
    q = (request.GET.get("q") or "").strip()

    qs = (
        Product.objects
        .prefetch_related("variants__size")
        .order_by("-is_active", "name", "sku")
    )

    if q:
        qs = qs.filter(
            Q(sku__icontains=q)
            | Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(category__icontains=q)
            | Q(tag__icontains=q)
        )

    return JsonResponse({
        "ok": True,
        "results": [product_payload(request, p) for p in qs[:500]]
    })


def _as_int(value, field_name, minimum=0):
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} invalide.")

    if n < minimum:
        raise ValueError(f"{field_name} ne peut pas être inférieur à {minimum}.")

    return n


def _parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on", "oui"}


def _load_variants(raw):
    if not raw:
        return []

    try:
        variants = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("Liste des variantes invalide.")

    if not isinstance(variants, list):
        raise ValueError("variants_json doit être une liste.")

    cleaned = []
    seen = set()

    for row in variants:
        if not isinstance(row, dict):
            raise ValueError("Chaque variante doit être un objet.")

        label = str(row.get("size") or "").strip()

        if not label:
            continue

        key = label.lower()

        if key in seen:
            raise ValueError(f"Variante en double : {label}")

        stock = _as_int(row.get("stock_qty"), f"Stock {label}", 0)

        cleaned.append({
            "size": label,
            "stock_qty": stock,
        })

        seen.add(key)

    return cleaned


@user_passes_test(can_manage_inventory)
@require_POST
def admin_save_product_api(request):
    data = request.POST

    old_sku = (data.get("old_sku") or "").strip()
    sku = (data.get("sku") or "").strip().upper()
    name = (data.get("name") or "").strip()

    if not sku:
        return JsonResponse({"ok": False, "error": "SKU obligatoire."}, status=400)

    if not name:
        return JsonResponse({"ok": False, "error": "Nom produit obligatoire."}, status=400)

    variant_type = (data.get("variant_type") or "shoe_size").strip()
    allowed_types = {key for key, _ in Product.VARIANT_TYPES}

    if variant_type not in allowed_types:
        return JsonResponse({"ok": False, "error": "Type de variante invalide."}, status=400)

    try:
        retail_price = _as_int(data.get("retail_price"), "Prix public", 0)
        reseller_price = _as_int(data.get("reseller_price"), "Prix revendeur", 0)
        reseller_moq = _as_int(data.get("reseller_moq"), "MOQ revendeur", 1)
        variants = _load_variants(data.get("variants_json") or "[]")
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    with transaction.atomic():
        if old_sku:
            product = (
                Product.objects
                .select_for_update()
                .filter(sku__iexact=old_sku)
                .first()
            )

            if not product:
                return JsonResponse({"ok": False, "error": "Produit à modifier introuvable."}, status=404)

            if sku.lower() != old_sku.lower():
                exists = Product.objects.filter(sku__iexact=sku).exclude(pk=product.pk).exists()
                if exists:
                    return JsonResponse({"ok": False, "error": "Ce SKU existe déjà."}, status=400)
        else:
            if Product.objects.filter(sku__iexact=sku).exists():
                return JsonResponse({"ok": False, "error": "Ce SKU existe déjà."}, status=400)

            product = Product(sku=sku)

        product.sku = sku
        product.name = name
        product.brand = (data.get("brand") or "").strip()
        product.category = (data.get("category") or "").strip()
        product.tag = (data.get("tag") or "").strip()
        product.description = (data.get("description") or "").strip()
        product.retail_price = retail_price
        product.reseller_price = reseller_price
        product.reseller_moq = reseller_moq
        product.variant_type = variant_type
        product.is_active = _parse_bool(data.get("is_active"))

        image = request.FILES.get("image")
        if image:
            product.image = image

        try:
            product.save()
        except IntegrityError:
            return JsonResponse({"ok": False, "error": "SKU déjà utilisé."}, status=400)

        submitted_size_ids = set()

        for row in variants:
            size, _ = Size.objects.get_or_create(label=row["size"])

            Variant.objects.update_or_create(
                product=product,
                size=size,
                defaults={"stock_qty": row["stock_qty"]},
            )

            submitted_size_ids.add(size.id)

        # On ne supprime pas les anciennes variantes.
        # Si elles ont déjà été utilisées dans une commande, supprimer casserait l'historique.
        # Donc une variante retirée du formulaire passe simplement à stock 0.
        if old_sku and submitted_size_ids:
            product.variants.exclude(size_id__in=submitted_size_ids).update(stock_qty=0)

    product = Product.objects.prefetch_related("variants__size").get(pk=product.pk)

    return JsonResponse({
        "ok": True,
        "product": product_payload(request, product)
    })


@user_passes_test(can_manage_inventory)
@require_POST
def admin_toggle_product_api(request, sku):
    product = Product.objects.filter(sku__iexact=(sku or "").strip()).first()

    if not product:
        return JsonResponse({"ok": False, "error": "Produit introuvable."}, status=404)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    if "is_active" in body:
        product.is_active = bool(body.get("is_active"))
    else:
        product.is_active = not product.is_active

    product.save(update_fields=["is_active"])

    return JsonResponse({
        "ok": True,
        "sku": product.sku,
        "is_active": product.is_active,
    })