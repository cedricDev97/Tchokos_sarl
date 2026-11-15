from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0012_order_whatsapp_reservation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderCostSheet",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("courier_cost", models.PositiveIntegerField(blank=True, null=True, verbose_name="Coût livreur FCFA")),
                ("payment_fee", models.PositiveIntegerField(blank=True, null=True, verbose_name="Frais encaissement FCFA")),
                ("other_cost", models.PositiveIntegerField(blank=True, null=True, verbose_name="Autres coûts variables FCFA")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cost_sheet", to="orders.order")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OrderCostRevision",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("previous_values", models.JSONField(default=dict)),
                ("new_values", models.JSONField(default=dict)),
                ("reason", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cost_revisions", to="orders.order")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
