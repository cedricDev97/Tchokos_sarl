from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0009_paymentstatuslog"),
    ]
    operations = [
        migrations.CreateModel(
            name="CheckoutAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("request_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="checkout_attempt", to="orders.order")),
            ],
        ),
    ]
