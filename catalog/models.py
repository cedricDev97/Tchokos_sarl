from django.db import models

class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=80, blank=True)  # Sneakers, Sandales, Sport...
    tag = models.CharField(max_length=60, blank=True)       # Arrivage, Best-seller...
    description = models.TextField(blank=True)

    retail_price = models.PositiveIntegerField(default=0)   # FCFA
    reseller_price = models.PositiveIntegerField(default=0) # FCFA
    reseller_moq = models.PositiveIntegerField(default=1)   # MOQ revendeur

    image = models.ImageField(upload_to="products/", blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.sku} — {self.name}"    


class Size(models.Model):
    value = models.PositiveSmallIntegerField(unique=True)   # 38, 39, 40...
    def __str__(self):
        return str(self.value)


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    stock_qty = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("product", "size")

    def __str__(self):
        return f"{self.product.sku} T{self.size.value} ({self.stock_qty})"


# Create your models here.
