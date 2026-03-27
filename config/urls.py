from django.contrib import admin
from django.urls import path, include
from storefront.views import home
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("api/", include("catalog.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

