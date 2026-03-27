import json
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError

from .models import ResellerApplication, UserProfile
from .permissions import (
    is_admin,
    is_super_admin,
    can_manage_orders,
    can_manage_payments,
    can_manage_inventory,
    can_manage_resellers,
    build_admin_permissions,
)




def ensure_group(name: str) -> Group:
    g, _ = Group.objects.get_or_create(name=name)
    return g


def get_role(user) -> str:
    if is_admin(user):
        return "admin"
    if user.groups.filter(name="reseller").exists():
        return "reseller"
    return "visitor"


@login_required
@require_http_methods(["GET"])
def me_api(request):
    phone = ""
    if hasattr(request.user, "profile"):
        phone = request.user.profile.phone or ""

    return JsonResponse({
        "ok": True,
        "authenticated": True,
        "username": request.user.username,
        "role": get_role(request.user),
        "phone": phone,
        "permissions": build_admin_permissions(request.user) if get_role(request.user) == "admin" else {
            "super_admin": False,
            "orders": False,
            "payments": False,
            "inventory": False,
            "resellers": False,
        }
    })


@csrf_protect
@require_http_methods(["POST"])
def login_api(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if not username or not password:
        return JsonResponse({"ok": False, "error": "username/password requis"}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"ok": False, "error": "Identifiants invalides"}, status=401)

    login(request, user)
    return JsonResponse({"ok": True, "role": get_role(user), "username": user.username})

@csrf_protect
@require_http_methods(["POST"])
def register_api(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    username = (body.get("username") or "").strip()
    phone = (body.get("phone") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not phone or not password:
        return JsonResponse({"ok": False, "error": "username, phone et password requis"}, status=400)

    if len(password) < 6:
        return JsonResponse({"ok": False, "error": "Le mot de passe doit faire au moins 6 caractères"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"ok": False, "error": "Ce nom d'utilisateur existe déjà"}, status=400)

    try:
        user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(user=user, phone=phone)
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "Impossible de créer le compte"}, status=400)

    login(request, user)

    return JsonResponse({
        "ok": True,
        "authenticated": True,
        "username": user.username,
        "role": get_role(user),
    })


@csrf_protect
@require_http_methods(["POST"])
def logout_api(request):
    logout(request)
    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["GET"])
def reseller_status_api(request):
    app = ResellerApplication.objects.filter(user=request.user).first()
    return JsonResponse({"ok": True, "status": (app.status if app else "none")})


@login_required
@csrf_protect
@require_http_methods(["POST"])
def reseller_apply_api(request):
    if request.user.is_staff or request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Admin ne peut pas postuler."}, status=403)
    # si déjà revendeur
    if request.user.groups.filter(name="reseller").exists():
        return JsonResponse({"ok": False, "error": "Déjà revendeur."}, status=400)

    if ResellerApplication.objects.filter(user=request.user).exists():
        return JsonResponse({"ok": False, "error": "Une demande est en cours."}, status=400)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    full_name = (body.get("full_name") or "").strip()
    phone = (body.get("phone") or "").strip()

    if not full_name or not phone:
        return JsonResponse({"ok": False, "error": "Nom et téléphone obligatoires."}, status=400)

    defaults = {
        "status": "pending",
        "full_name": full_name,
        "phone": phone,
        "city": (body.get("city") or "").strip(),
        "shop_name": (body.get("shop_name") or "").strip(),
        "instagram": (body.get("instagram") or "").strip(),
        "monthly_volume": int(body.get("monthly_volume") or 0),
        "message": (body.get("message") or "").strip(),
    }

    app, _ = ResellerApplication.objects.update_or_create(
        user=request.user,
        defaults=defaults
    )

    return JsonResponse({"ok": True, "status": app.status})

@user_passes_test(can_manage_resellers)
@login_required
@require_http_methods(["GET"])
def admin_reseller_applications_api(request):
    if not is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    status = (request.GET.get("status") or "").strip()
    qs = ResellerApplication.objects.select_related("user").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)

    results = []
    for a in qs[:200]:
        results.append({
            "id": a.id,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "decided_at": a.decided_at.isoformat() if getattr(a, "decided_at", None) else None,
            "user": {"id": a.user_id, "username": a.user.username},
            "full_name": a.full_name,
            "phone": a.phone,
            "city": a.city,
            "shop_name": a.shop_name,
            "instagram": a.instagram,
            "monthly_volume": a.monthly_volume,
            "message": a.message,
        })

    return JsonResponse({"ok": True, "results": results})

@user_passes_test(can_manage_resellers)
@login_required
@csrf_protect
@require_http_methods(["POST"])
def admin_approve_reseller_api(request, app_id: int):
    if not is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    a = ResellerApplication.objects.select_related("user").filter(id=app_id).first()
    if not a:
        return JsonResponse({"ok": False, "error": "Application introuvable"}, status=404)

    reseller_group = ensure_group("reseller")
    a.user.groups.add(reseller_group)

    a.status = "approved"
    if hasattr(a, "decided_at"):
        a.decided_at = timezone.now()
    a.save()

    return JsonResponse({"ok": True, "status": a.status, "username": a.user.username})

@user_passes_test(can_manage_resellers)
@login_required
@csrf_protect
@require_http_methods(["POST"])
def admin_reject_reseller_api(request, app_id: int):
    if not is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    a = ResellerApplication.objects.select_related("user").filter(id=app_id).first()
    if not a:
        return JsonResponse({"ok": False, "error": "Application introuvable"}, status=404)

    a.status = "rejected"
    if hasattr(a, "decided_at"):
        a.decided_at = timezone.now()
    a.save()

    return JsonResponse({"ok": True, "status": a.status, "username": a.user.username})
