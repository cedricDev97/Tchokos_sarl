from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0011_codcollection")]

    operations = [
        migrations.AddField(
            model_name="order", name="checkout_channel",
            field=models.CharField(
                max_length=20, default="web", db_index=True,
                choices=[("web", "Site"), ("whatsapp", "WhatsApp")],
            ),
        ),
        migrations.AddField(
            model_name="order", name="reservation_expires_at",
            field=models.DateTimeField(null=True, blank=True, db_index=True),
        ),
    ]
