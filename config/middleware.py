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
