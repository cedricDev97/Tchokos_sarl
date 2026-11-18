"""Expiration des sessions administrateur eKAKO."""
from datetime import timedelta

from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone


class AdminSessionSecurityMiddleware:
    IDLE_LIMIT = timedelta(minutes=30)
    ABSOLUTE_LIMIT = timedelta(hours=8)
    CREATED_KEY = "_ekako_admin_created"
    ACTIVE_KEY = "_ekako_admin_last_active"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        from accounts.permissions import is_admin

        if not (user.is_staff or is_admin(user)):
            return self.get_response(request)

        now = timezone.now()
        session = request.session
        created = session.get(self.CREATED_KEY)
        active = session.get(self.ACTIVE_KEY)

        try:
            created_at = (
                timezone.datetime.fromisoformat(created)
                if created else now
            )
            active_at = (
                timezone.datetime.fromisoformat(active)
                if active else now
            )
            if (
                timezone.is_naive(created_at)
                or timezone.is_naive(active_at)
            ):
                raise ValueError("Invalid session timestamps")
            expired = (
                now - active_at >= self.IDLE_LIMIT
                or now - created_at >= self.ABSOLUTE_LIMIT
                or created_at > now
                or active_at > now
            )
        except (ValueError, TypeError, OverflowError):
            expired = True

        if expired:
            logout(request)

            # Une ancienne session expirée ne doit pas
            # empêcher une nouvelle authentification.
            if (
                request.path_info == "/api/admin/login/"
                and request.method == "POST"
            ):
                return self.get_response(request)

            if request.path_info.startswith("/api/admin/"):
                response = JsonResponse(
                    {"ok": False, "error": "Session expirée"},
                    status=401,
                )
                response["Cache-Control"] = "no-store"
                return response
            return self.get_response(request)

        session[self.CREATED_KEY] = (
            created or now.isoformat()
        )
        session[self.ACTIVE_KEY] = now.isoformat()
        session.set_expiry(0)

        response = self.get_response(request)
        if request.path_info.startswith("/api/admin/"):
            response["Cache-Control"] = "no-store"
        return response
