from django.contrib import admin
from .models import CODCollection, OrderCostSheet, OrderCostRevision, CourierPayout

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


@admin.register(OrderCostSheet)
class OrderCostSheetAdmin(admin.ModelAdmin):
    list_display = ("order", "courier_cost", "payment_fee", "other_cost", "updated_by", "updated_at")
    search_fields = ("order__order_no",)
    readonly_fields = ("order", "courier_cost", "payment_fee", "other_cost", "updated_by", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderCostRevision)
class OrderCostRevisionAdmin(admin.ModelAdmin):
    list_display = ("order", "reason", "changed_by", "created_at")
    search_fields = ("order__order_no", "reason")
    readonly_fields = ("order", "previous_values", "new_values", "reason", "changed_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CourierPayout)
class CourierPayoutAdmin(admin.ModelAdmin):
    """Journal consultable uniquement : seule l'API métier crée des règlements."""
    list_display = ("order", "courier_name", "amount", "method", "reference", "recorded_at", "recorded_by")
    list_filter = ("method", "recorded_at")
    search_fields = ("order__order_no", "reference", "courier_name")
    readonly_fields = ("order", "courier_name", "amount", "method", "reference", "note", "recorded_by", "recorded_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
