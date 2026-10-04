from django.urls import path

from .views import (
    products_api,
    admin_products_api,
    admin_save_product_api,
    admin_toggle_product_api,
)

urlpatterns = [
    path("products/", products_api, name="products_api"),
    path("admin/products/", admin_products_api, name="admin_products_api"),
    path("admin/products/save/", admin_save_product_api, name="admin_save_product_api"),
    path("admin/products/<str:sku>/toggle/", admin_toggle_product_api, name="admin_toggle_product_api"),
]