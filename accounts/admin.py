from django.contrib import admin
from .models import ResellerApplication

@admin.register(ResellerApplication)
class ResellerApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "city", "monthly_volume", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("user__username", "phone", "full_name", "shop_name", "instagram")


# Register your models here.
