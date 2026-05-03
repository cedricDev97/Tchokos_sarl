from django.urls import path
from . import views
from .views import (
    checkout_api,
    track_api,
    admin_stats_api,
    admin_orders_api,
    admin_update_status_api,
    admin_analytics_api,
    admin_inventory_api,
    admin_adjust_stock_api,
)

urlpatterns = [
    path("checkout/", checkout_api, name="checkout_api"),
    path("track/<str:order_no>/", track_api, name="track_api"),

    path("admin/stats/", admin_stats_api, name="admin_stats_api"),
    path("admin/orders/", admin_orders_api, name="admin_orders_api"),
    path("admin/order/<str:order_no>/", views.admin_order_detail_api, name="admin_order_detail_api"),
    path("admin/order/<str:order_no>/status/", admin_update_status_api, name="admin_update_status_api"),
    path("admin/order/<str:order_no>/payment-status/", views.admin_update_payment_status_api, name="admin_update_payment_status_api"),
    path("admin/orders/<str:order_no>/timeline/", views.admin_order_timeline_api, name="admin_order_timeline_api"),

    path("admin/analytics/", admin_analytics_api, name="admin_analytics_api"),
    path("admin/inventory/", admin_inventory_api, name="admin_inventory_api"),
    path("admin/inventory/adjust/", admin_adjust_stock_api, name="admin_adjust_stock_api"),

    path("reseller/me/orders/", views.reseller_my_orders_api, name="reseller_my_orders_api"),
    path("reseller/me/orders/<str:order_no>/", views.reseller_order_detail_api, name="reseller_order_detail_api"),
    path("reseller/me/orders/<str:order_no>/timeline/", views.reseller_order_timeline_api, name="reseller_order_timeline_api"),
    path("reseller/me/stats/", views.reseller_stats_api, name="reseller_stats_api"),
    path("reseller/me/top-products/", views.reseller_top_products_api, name="reseller_top_products_api"),]