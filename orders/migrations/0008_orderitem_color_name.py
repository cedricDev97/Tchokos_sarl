# eKAKO ORDER COLORS V1
from django.db import migrations, models


def fill_legacy_order_colors(apps, schema_editor):
    """Recopie, si disponible, la couleur actuellement liée au SKU historique.

    Une couleur supprimée ou modifiée avant la migration n'est pas récupérable.
    """
    OrderItem = apps.get_model('orders', 'OrderItem')
    alias = schema_editor.connection.alias
    items = OrderItem.objects.using(alias).select_related('variant__product').filter(color_name='')
    for item in items.iterator(chunk_size=200):
        color = (getattr(item.variant.product, 'color_name', '') or '').strip()[:50]
        if color:
            OrderItem.objects.using(alias).filter(pk=item.pk).update(color_name=color)


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0007_alter_orderitem_size_value'),
        ('catalog', '0006_product_color_name_product_style_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='color_name',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.RunPython(fill_legacy_order_colors, migrations.RunPython.noop),
    ]
