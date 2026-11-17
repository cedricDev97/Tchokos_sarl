from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

class EkakoMaintenanceMiddleware:
    """Affiche 503, préserve l'administration et les assets."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.EKAKO_MAINTENANCE:
            return self.get_response(request)
        path = request.path_info
        if path == "/healthz/":
            return self.get_response(request)
        if path.startswith(("/admin/", "/static/", "/media/")) or path == "/admin":
            return self.get_response(request)
        if path in ("/api/admin/login/", "/api/admin/logout/", "/api/admin/me/"):
            return self.get_response(request)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            from accounts.permissions import is_admin
            if is_admin(user) and (path in ("/", "/boutique/") or path.startswith("/api/admin/")):
                return self.get_response(request)
        if path.startswith("/api/"):
            response = JsonResponse({"ok": False, "code": "maintenance", "error": "Service temporairement indisponible."}, status=503)
        else:
            response = render(request, "errors/503.html", status=503)
        response["Cache-Control"] = "no-store"
        response["Retry-After"] = "600"
        return response


class ProductSaveDiagnosticMiddleware:
    """Journalise uniquement les exceptions imprévues du formulaire produit.

    Aucun contenu du formulaire, nom de fichier, identifiant client, exception
    détaillée ou credential n'est transmis dans notre journal de diagnostic.
    Django garde le traitement standard HTTP 500 avec DEBUG=False.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if (request.method != "POST"
                or request.path_info != "/api/admin/products/save/"):
            return None

        import logging
        import traceback

        frames = traceback.extract_tb(exception.__traceback__)
        # Fichier, fonction, ligne seulement : jamais les lignes sources,
        # l'exception.__str__ ou des valeurs métier.
        location = " > ".join(
            f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}:{frame.name}"
            for frame in frames[-8:]
        ) or "unavailable"
        stage = getattr(request, "_ekako_product_save_stage", "before_view")
        logging.getLogger("ekako.product_save").error(
            "EKAKO_PRODUCT_SAVE_FAILURE stage=%s exception_type=%s call_stack=%s",
            stage, type(exception).__name__, location,
        )
        return None


class DjangoAdminLoginThrottleMiddleware:
    """Limite les échecs sur /admin/login/ avec les compteurs SQL existants.

    L'état est partagé via PostgreSQL entre les instances Render.
    Les tentatives CSRF refusées (403) ne sont pas comptées comme
    échecs de mot de passe. Aucun identifiant en clair n'est journalisé.
    """

    LOGIN_PATH = "/admin/login/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST" or request.path_info != self.LOGIN_PATH:
            return self.get_response(request)

        from django.http import HttpResponse
        from accounts.login_throttle import (
            clear_successful_login,
            login_retry_after,
            record_failed_login,
        )

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        # Ne jamais enregistrer les données du formulaire ou le mot de passe.
        if not username or not password:
            return self.get_response(request)

        throttle_identity = "django-admin:" + username
        retry_after = login_retry_after(request, throttle_identity)
        if retry_after:
            response = HttpResponse(
                "Trop de tentatives de connexion. Réessayez plus tard.",
                status=429,
                content_type="text/plain; charset=utf-8",
            )
            response["Retry-After"] = str(retry_after)
            response["Cache-Control"] = "no-store"
            return response

        response = self.get_response(request)
        # Django Admin LoginView : formulaire invalide = HTTP 200 ;
        # authentification réussie = redirection + utilisateur authentifié.
        if (response.status_code in (301, 302, 303)
                and request.user.is_authenticated and request.user.is_staff
                and request.user.is_active):
            clear_successful_login(request, throttle_identity)
        elif response.status_code == 200 and not request.user.is_authenticated:
            record_failed_login(request, throttle_identity)
        return response
