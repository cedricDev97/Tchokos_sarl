from django.shortcuts import render
from django.conf import settings
from catalog.models import Product

def home(request):
    products = Product.objects.filter(is_active=True).order_by("-id")[:6]
    return render(request, "storefront/landing.html", {"featured_products": products, "turnstile_enabled": settings.EKAKO_TURNSTILE_ENABLED, "turnstile_sitekey": settings.EKAKO_TURNSTILE_SITE_KEY})



# Create your views here.


def boutique(request):
    return render(request, "storefront/index.html", {"turnstile_enabled": settings.EKAKO_TURNSTILE_ENABLED, "turnstile_sitekey": settings.EKAKO_TURNSTILE_SITE_KEY})
