from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("catalog", "0006_product_color_name_product_style_group"),
        ("orders", "0009_paymentstatuslog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name="Supplier", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=150, unique=True, verbose_name="Nom commerçant")),
            ("contact_name", models.CharField(blank=True, max_length=120, verbose_name="Contact")),
            ("phone", models.CharField(blank=True, max_length=30, verbose_name="Téléphone")),
            ("city", models.CharField(default="Yaounde", max_length=80, verbose_name="Ville")),
            ("quarter", models.CharField(blank=True, max_length=120, verbose_name="Quartier")),
            ("pickup_address", models.CharField(blank=True, max_length=255, verbose_name="Point de collecte")),
            ("status", models.CharField(choices=[("active", "Actif"), ("onboarding", "En cours d'intégration"), ("inactive", "Inactif")], default="onboarding", max_length=20)),
            ("notes", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="SupplierOffer", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("purchase_price", models.PositiveIntegerField(blank=True, null=True, verbose_name="Coût d'achat unitaire FCFA")),
            ("availability_state", models.CharField(choices=[("to_check", "À vérifier"), ("reported", "Déclarée disponible"), ("unavailable", "Indisponible")], default="to_check", max_length=20)),
            ("availability_checked_at", models.DateTimeField(blank=True, null=True)),
            ("pickup_eta_hours", models.PositiveSmallIntegerField(default=24, verbose_name="Délai estimé de collecte (heures)")),
            ("notes", models.TextField(blank=True)),
            ("product", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_offer", to="catalog.product")),
            ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="offers", to="sourcing.supplier")),
        ]),
        migrations.CreateModel(name="ProcurementLine", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("unit_cost", models.PositiveIntegerField(blank=True, null=True, verbose_name="Prix fournisseur figé, FCFA")),
            ("status", models.CharField(choices=[("unassigned", "Fournisseur non attribué"), ("to_confirm", "À confirmer auprès du commerçant"), ("confirmed", "Réservé par le commerçant"), ("collected", "Récupéré par eKAKO"), ("unavailable", "Indisponible chez le commerçant"), ("cancelled", "Annulé")], db_index=True, default="unassigned", max_length=20)),
            ("pickup_note", models.TextField(blank=True, verbose_name="Collecte / observations")),
            ("confirmed_at", models.DateTimeField(blank=True, null=True)),
            ("collected_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("order_item", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="procurement", to="orders.orderitem")),
            ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="procurements", to="sourcing.supplier")),
        ]),
        migrations.CreateModel(name="SupplierPayment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("amount", models.PositiveIntegerField(verbose_name="Montant réglé, FCFA")),
            ("method", models.CharField(choices=[("cash", "Espèces"), ("momo", "MTN MoMo"), ("om", "Orange Money"), ("bank", "Virement")], max_length=10)),
            ("reference", models.CharField(blank=True, max_length=120)),
            ("paid_at", models.DateTimeField(default=django.utils.timezone.now)),
            ("note", models.CharField(blank=True, max_length=255)),
            ("procurement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_payments", to="sourcing.procurementline")),
            ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="DeliveryTask", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(choices=[("planned", "À préparer"), ("ready", "Colis prêt"), ("assigned", "Livreur affecté"), ("out_for_delivery", "En cours de livraison"), ("delivered", "Remis au client"), ("failed", "Livraison échouée"), ("returned", "Retour")], db_index=True, default="planned", max_length=25)),
            ("courier_name", models.CharField(blank=True, max_length=120, verbose_name="Livreur")),
            ("courier_phone", models.CharField(blank=True, max_length=30, verbose_name="Téléphone livreur")),
            ("pickup_note", models.TextField(blank=True, verbose_name="Regroupement des produits")),
            ("delivery_note", models.TextField(blank=True, verbose_name="Preuve / incident / observations")),
            ("delivered_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_task", to="orders.order")),
        ]),
    ]
