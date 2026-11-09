"""eKAKO modèle B : fournisseurs, collecte à la commande, marges et livraison.

Le stock catalogue est une disponibilité déclarée (chez un partenaire), pas un stock possédé.
Les demandes d'approvisionnement sont créées à la commande; aucun fournisseur n'est
payé automatiquement par cette application.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Supplier(models.Model):
    STATUS_CHOICES = [("active", "Actif"), ("onboarding", "En cours d'intégration"), ("inactive", "Inactif")]
    name = models.CharField("Nom commerçant", max_length=150, unique=True)
    contact_name = models.CharField("Contact", max_length=120, blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    city = models.CharField("Ville", max_length=80, default="Yaounde")
    quarter = models.CharField("Quartier", max_length=120, blank=True)
    pickup_address = models.CharField("Point de collecte", max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="onboarding")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierOffer(models.Model):
    """Une fiche commerciale fournisseur par SKU/couleur pour la V1.
    L'offre ne garantit pas la disponibilité au moment de l'achat client.
    """
    AVAILABILITY = [("to_check", "À vérifier"), ("reported", "Déclarée disponible"), ("unavailable", "Indisponible")]
    product = models.OneToOneField("catalog.Product", on_delete=models.PROTECT, related_name="supplier_offer")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="offers")
    purchase_price = models.PositiveIntegerField("Coût d'achat unitaire FCFA", null=True, blank=True)
    availability_state = models.CharField(max_length=20, choices=AVAILABILITY, default="to_check")
    availability_checked_at = models.DateTimeField(null=True, blank=True)
    pickup_eta_hours = models.PositiveSmallIntegerField("Délai estimé de collecte (heures)", default=24)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.sku} chez {self.supplier.name}"


class ProcurementLine(models.Model):
    STATUS_CHOICES = [
        ("unassigned", "Fournisseur non attribué"),
        ("to_confirm", "À confirmer auprès du commerçant"),
        ("confirmed", "Réservé par le commerçant"),
        ("collected", "Récupéré par eKAKO"),
        ("unavailable", "Indisponible chez le commerçant"),
        ("cancelled", "Annulé"),
    ]
    order_item = models.OneToOneField("orders.OrderItem", on_delete=models.PROTECT, related_name="procurement")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="procurements")
    unit_cost = models.PositiveIntegerField("Prix fournisseur figé, FCFA", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unassigned", db_index=True)
    pickup_note = models.TextField("Collecte / observations", blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def cost_total(self):
        return self.unit_cost * self.order_item.qty if self.unit_cost is not None else None

    @property
    def gross_margin(self):
        total = self.cost_total
        return self.order_item.line_total - total if total is not None else None

    @property
    def payable_balance(self):
        total = self.cost_total
        if total is None:
            return None
        paid = self.supplier_payments.aggregate(s=Sum("amount"))["s"] or 0
        return total - paid

    def clean(self):
        if self.status in {"to_confirm", "confirmed", "collected"} and self.supplier_id is None:
            raise ValidationError({"supplier": "Attribue un commerçant avant cette étape."})
        if self.status in {"confirmed", "collected"} and self.unit_cost is None:
            raise ValidationError({"unit_cost": "Le prix fournisseur doit être connu avant la réservation."})

    def save(self, *args, **kwargs):
        if self.status in {"confirmed", "collected"} and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        if self.status == "collected" and not self.collected_at:
            self.collected_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_item.order.order_no} · {self.order_item.sku} · {self.get_status_display()}"


class SupplierPayment(models.Model):
    """Écriture MANUELLE d'un paiement fournisseur, sans transfert d'argent."""
    PAYMENT_METHODS = [("cash", "Espèces"), ("momo", "MTN MoMo"), ("om", "Orange Money"), ("bank", "Virement")]
    procurement = models.ForeignKey(ProcurementLine, on_delete=models.PROTECT, related_name="supplier_payments")
    amount = models.PositiveIntegerField("Montant réglé, FCFA")
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=255, blank=True)

    def clean(self):
        if self.amount is None or self.amount < 1:
            raise ValidationError({"amount": "Montant supérieur à zéro obligatoire."})
        if not self.procurement_id:
            return
        p = self.procurement
        if p.supplier_id is None or p.unit_cost is None:
            raise ValidationError("Commerçant et prix fournisseur obligatoires pour enregistrer le règlement.")
        already = p.supplier_payments.exclude(pk=self.pk).aggregate(s=Sum("amount"))["s"] or 0
        if already + self.amount > p.cost_total:
            raise ValidationError({"amount": "Total des règlements supérieur au coût fournisseur de cette ligne."})

    def __str__(self):
        return f"{self.amount} FCFA · {self.procurement.order_item.sku}"


class DeliveryTask(models.Model):
    STATUS_CHOICES = [
        ("planned", "À préparer"),
        ("ready", "Colis prêt"),
        ("assigned", "Livreur affecté"),
        ("out_for_delivery", "En cours de livraison"),
        ("delivered", "Remis au client"),
        ("failed", "Livraison échouée"),
        ("returned", "Retour"),
    ]
    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="delivery_task")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="planned", db_index=True)
    courier_name = models.CharField("Livreur", max_length=120, blank=True)
    courier_phone = models.CharField("Téléphone livreur", max_length=30, blank=True)
    pickup_note = models.TextField("Regroupement des produits", blank=True)
    delivery_note = models.TextField("Preuve / incident / observations", blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.status in {"assigned", "out_for_delivery", "delivered"} and not self.courier_name.strip():
            raise ValidationError({"courier_name": "Indique le livreur affecté."})

    def save(self, *args, **kwargs):
        if self.status == "delivered" and not self.delivered_at:
            self.delivered_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order.order_no} · {self.get_status_display()}"
