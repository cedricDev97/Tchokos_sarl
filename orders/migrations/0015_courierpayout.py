from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0014_alter_ordercostrevision_id_alter_ordercostsheet_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CourierPayout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("courier_name", models.CharField(max_length=120)),
                ("amount", models.PositiveIntegerField(verbose_name="Montant versé FCFA")),
                ("method", models.CharField(max_length=10, choices=[
                    ("cash", "Espèces"), ("momo", "MTN MoMo"),
                    ("om", "Orange Money"), ("bank", "Virement"),
                ])),
                ("reference", models.CharField(max_length=120, unique=True)),
                ("note", models.CharField(max_length=255, blank=True)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name="courier_payouts", to="orders.order")),
                ("recorded_by", models.ForeignKey(blank=True, null=True,
                                                   on_delete=django.db.models.deletion.SET_NULL,
                                                   to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
    ]
