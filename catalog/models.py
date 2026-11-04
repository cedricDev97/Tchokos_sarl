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

    # EKAKO_COULEURS_V1 : un SKU par couleur, stock par taille conservé
    style_group = models.CharField(max_length=70, blank=True, db_index=True)
    color_name = models.CharField(max_length=50, blank=True)

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

# eKAKO_GALERIE_V1 — photographies secondaires, image principale conservée
class ProductGalleryImage(models.Model):
    product = models.ForeignKey(
        Product, related_name="gallery_images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="products/gallery/")
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.product.sku} — photo {self.pk}"
