from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0010_checkoutattempt"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CODCollection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.PositiveIntegerField(verbose_name="Montant perçu (FCFA)")),
                ("reference", models.CharField(max_length=80, unique=True, verbose_name="Référence d'encaissement")),
                ("courier_name", models.CharField(max_length=120, verbose_name="Livreur collecteur")),
                ("note", models.CharField(blank=True, max_length=255)),
                ("collected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cod_collection", to="orders.order")),
                ("recorded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cod_collections_recorded", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cod_collections_verified", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Encaissement à la livraison", "verbose_name_plural": "Encaissements à la livraison", "ordering": ["-collected_at"]},
        ),
    ]
