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
