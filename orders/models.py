from django.db import models
from catalog.models import Variant
from django.conf import settings

class Order(models.Model):
    ORDER_STEPS = [
        ("received", "Commande reçue"),
        ("preparing", "Préparation"),
        ("shipped", "Expédiée"),
        ("delivered", "Livrée"),
        ("cancelled", "Annulée"),
        ("failed", "Échouée"),
    ]
    PAYMENT_STATES = [
        ("unpaid", "Non payé"),
        ("pending", "En attente"),
        ("paid", "Payé"),
        ("failed", "Échoué"),
    ]


    order_no = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STEPS, default="received")

    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=30)
    city = models.CharField(max_length=80)
    quarter = models.CharField(max_length=120)
    address = models.CharField(max_length=255)

    pay_method = models.CharField(max_length=80, default="MTN Mobile Money")

    payment_state = models.CharField(max_length=20, choices=PAYMENT_STATES, default="unpaid")
    payment_reference = models.CharField(max_length=120, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)

    shipping_fee = models.PositiveIntegerField(default=0)
    subtotal = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=20, default="retail")

    user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="orders"
    )


    def __str__(self):
        return self.order_no


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT)

    sku = models.CharField(max_length=40)
    product_name = models.CharField(max_length=200)
    size_value = models.PositiveSmallIntegerField()

    unit_price = models.PositiveIntegerField(default=0)  # IMPORTANT
    qty = models.PositiveIntegerField(default=1)
    line_total = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.order.order_no} - {self.sku} T{self.size_value} x{self.qty}"
    

class OrderStatusLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_logs")
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


# Create your models here.
