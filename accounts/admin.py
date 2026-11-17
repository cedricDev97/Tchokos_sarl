from django.contrib import admin
from .models import ResellerApplication

@admin.register(ResellerApplication)
class ResellerApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "city", "monthly_volume", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("user__username", "phone", "full_name", "shop_name", "instagram")


# Register your models here.


# Accès à la gestion des identités et groupes Django réservé au superuser.
# Une simple permission auth.change_user ou auth.change_group ne doit pas
# suffire pour s'attribuer les rôles métier privilégiés d'eKAKO.
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin, GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group


class SuperuserIdentityAdminMixin:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


# django.contrib.auth.admin enregistre ces deux modèles en premier.
admin.site.unregister(get_user_model())
admin.site.unregister(Group)


@admin.register(get_user_model())
class ProtectedUserAdmin(SuperuserIdentityAdminMixin, DjangoUserAdmin):
    pass


@admin.register(Group)
class ProtectedGroupAdmin(SuperuserIdentityAdminMixin, DjangoGroupAdmin):
    pass
