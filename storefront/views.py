from django.shortcuts import render
from catalog.models import Product

def home(request):
    products = Product.objects.filter(is_active=True).order_by("-id")[:6]
    return render(request, "storefront/landing.html", {"featured_products": products})



# Create your views here.


def boutique(request):
    return render(request, "storefront/index.html")
