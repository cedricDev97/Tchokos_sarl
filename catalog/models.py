from django.db import models


class Product(models.Model):
    VARIANT_TYPES = [
        ("shoe_size", "Pointure chaussure"),
        ("clothing_size", "Taille vêtement"),
        ("color", "Couleur"),
        ("capacity", "Capacité"),
        ("unique", "Unique"),
    ]

    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=80, blank=True)  # Sneakers, Sandales, Textile, Sacs...
    tag = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)

    retail_price = models.PositiveIntegerField(default=0)
    reseller_price = models.PositiveIntegerField(default=0)
    reseller_moq = models.PositiveIntegerField(default=1)

    image = models.ImageField(upload_to="products/", blank=True, null=True)

    variant_type = models.CharField(
        max_length=30,
        choices=VARIANT_TYPES,
        default="shoe_size"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.sku} — {self.name}"


class Size(models.Model):
    label = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.label


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    stock_qty = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("product", "size")

    def __str__(self):
        return f"{self.product.sku} {self.size.label} ({self.stock_qty})"