"""Permissions JSON pour les API eKAKO."""
from functools import wraps

from django.http import JsonResponse


def api_permission_required(permission_check):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                response = JsonResponse(
                    {
                        "ok": False,
                        "error": "Authentification requise",
                    },
                    status=401,
                )
            elif not permission_check(user):
                response = JsonResponse(
                    {
                        "ok": False,
                        "error": "Accès non autorisé",
                    },
                    status=403,
                )
            else:
                return view(request, *args, **kwargs)

            response["Cache-Control"] = "no-store"
            return response

        return wrapped
    return decorator
