from django.contrib import admin
from .models import Product, Size, Variant, ProductGalleryImage


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


class ProductGalleryInline(admin.TabularInline):
    model = ProductGalleryImage
    extra = 1
    fields = ("image", "position")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "brand",
        "category",
        "style_group",  # EKAKO_COULEURS_V1
        "color_name",
        "variant_type",
        "retail_price",
        "reseller_price",
        "is_active",
    )
    search_fields = ("sku", "name", "brand", "category", "style_group", "color_name")
    list_filter = ("brand", "category", "variant_type", "is_active")
    inlines = [VariantInline, ProductGalleryInline]


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
