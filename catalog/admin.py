from django.contrib import admin
from .models import Product, Size, Variant


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "brand",
        "category",
        "variant_type",
        "retail_price",
        "reseller_price",
        "is_active",
    )
    search_fields = ("sku", "name", "brand", "category")
    list_filter = ("brand", "category", "variant_type", "is_active")
    inlines = [VariantInline]


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ("label",)
    search_fields = ("label",)
    ordering = ("label",)


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("product", "size", "stock_qty")
    list_filter = ("product__brand", "product__category", "product__variant_type")


# Register your models here.
