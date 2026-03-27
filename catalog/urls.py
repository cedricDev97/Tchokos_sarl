from django.urls import path
from .views import products_api

urlpatterns = [
    path("products/", products_api, name="products_api"),
]

