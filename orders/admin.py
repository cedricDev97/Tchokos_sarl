from django.contrib import admin
from .models import CODCollection

# Register your models here.


@admin.register(CODCollection)
class CODCollectionAdmin(admin.ModelAdmin):
    """Journal en lecture seule : l'API métier est le seul point d'enregistrement."""
    list_display = (
        "order", "reference", "amount", "courier_name", "collected_at",
        "recorded_by", "verified_at", "verified_by",
    )
    search_fields = ("order__order_no", "reference", "courier_name")
    list_filter = ("collected_at", "verified_at")
    readonly_fields = (
        "order", "amount", "reference", "courier_name", "note", "collected_at",
        "recorded_by", "verified_at", "verified_by",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
