# Aligne les identifiants automatiques avec l'etat des modeles Django 6.0.1.
# Migration purement declarative ; aucune donnee financiere n'est modifiee.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0013_order_financial_costs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ordercostrevision",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="ordercostsheet",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
