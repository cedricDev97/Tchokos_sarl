from django.http import JsonResponse
from .models import Product

def products_api(request):
    data = []
    qs = Product.objects.filter(is_active=True).prefetch_related("variants__size")
    for p in qs:
        data.append({
            "sku": p.sku,
            "name": p.name,
            "brand": p.brand,
            "category": p.category,
            "tag": p.tag,
            "description": p.description,
            "retail_price": p.retail_price,
            "reseller_price": p.reseller_price,
            "reseller_moq": p.reseller_moq,
            "image_url" : request.build_absolute_uri(p.image.url) if p.image else None,

            "variants": [
                {"size": v.size.value, "stock_qty": v.stock_qty}
                for v in p.variants.all()
            ]
        })
    return JsonResponse({"results": data})


# Create your views here.
