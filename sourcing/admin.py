from django.contrib import admin
from .models import Supplier, SupplierOffer, ProcurementLine, SupplierPayment, DeliveryTask


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_name", "phone", "city", "quarter", "status")
    list_filter = ("status", "city")
    search_fields = ("name", "contact_name", "phone", "quarter")


@admin.register(SupplierOffer)
class SupplierOfferAdmin(admin.ModelAdmin):
    list_display = ("product", "supplier", "purchase_price", "availability_state", "availability_checked_at", "pickup_eta_hours")
    list_filter = ("availability_state", "supplier")
    search_fields = ("product__sku", "product__name", "supplier__name")
    autocomplete_fields = ("product", "supplier")


@admin.register(ProcurementLine)
class ProcurementLineAdmin(admin.ModelAdmin):
    list_display = ("order_number", "item_sku", "supplier", "status", "unit_cost", "total_cost", "margin", "supplier_balance")
    list_filter = ("status", "supplier")
    search_fields = ("order_item__order__order_no", "order_item__sku", "supplier__name")
    readonly_fields = ("order_item", "created_at", "updated_at", "confirmed_at", "collected_at", "total_cost", "margin", "supplier_balance")
    list_select_related = ("order_item__order", "supplier")

    def order_number(self, obj):
        return obj.order_item.order.order_no
    order_number.short_description = "Commande"

    def item_sku(self, obj):
        return obj.order_item.sku
    item_sku.short_description = "SKU"

    def total_cost(self, obj):
        return obj.cost_total if obj.cost_total is not None else "À définir"
    total_cost.short_description = "Coût total FCFA"

    def margin(self, obj):
        return obj.gross_margin if obj.gross_margin is not None else "À définir"
    margin.short_description = "Marge brute FCFA"

    def supplier_balance(self, obj):
        return obj.payable_balance if obj.payable_balance is not None else "À définir"
    supplier_balance.short_description = "Reste à régler FCFA"


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("procurement", "amount", "method", "reference", "paid_at", "recorded_by")
    search_fields = ("procurement__order_item__order__order_no", "procurement__supplier__name", "reference")
    list_filter = ("method", "paid_at")
    readonly_fields = ("recorded_by",)
    autocomplete_fields = ("procurement",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "courier_name", "courier_phone", "delivered_at")
    list_filter = ("status",)
    search_fields = ("order__order_no", "courier_name", "courier_phone")
    readonly_fields = ("order", "created_at", "updated_at", "delivered_at")
