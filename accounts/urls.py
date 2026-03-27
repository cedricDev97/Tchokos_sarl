from django.urls import path
from . import views

urlpatterns = [
    # auth
    path("admin/me/", views.me_api, name="me_api"),
    path("admin/login/", views.login_api, name="login_api"),
    path("admin/logout/", views.logout_api, name="logout_api"),
    path("admin/register/", views.register_api, name="register_api"),

    # reseller onboarding
    path("reseller/status/", views.reseller_status_api, name="reseller_status_api"),
    path("reseller/apply/", views.reseller_apply_api, name="reseller_apply_api"),

    # admin validate reseller
    path("admin/reseller/applications/", views.admin_reseller_applications_api, name="admin_reseller_apps"),
    path("admin/reseller/applications/<int:app_id>/approve/", views.admin_approve_reseller_api, name="admin_reseller_approve"),
    path("admin/reseller/applications/<int:app_id>/reject/", views.admin_reject_reseller_api, name="admin_reseller_reject"),
]
