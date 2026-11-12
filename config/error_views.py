from django.http import JsonResponse
from django.shortcuts import render

def _display(request, status, text):
    if request.path.startswith("/api/"):
        return JsonResponse({"ok": False, "code": status, "error": text}, status=status)
    return render(request, f"errors/{status}.html", status=status)

def bad_request(request, exception=None):
    return _display(request, 400, "Requête incorrecte.")
def permission_denied(request, exception=None):
    return _display(request, 403, "Accès refusé.")
def page_not_found(request, exception=None):
    return _display(request, 404, "Page introuvable.")
def server_error(request):
    return _display(request, 500, "Erreur interne.")
