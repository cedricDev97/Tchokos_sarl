"""Tests isolés : uniquement sur la base temporaire du runner Django."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from catalog.models import Product, Size, Variant
from orders.models import Order, OrderItem


class OrderColorTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku='TEST-PULL-BLANC', name='Pull de test', brand='Test',
            style_group='TEST-PULL', color_name='Blanc',
            variant_type='clothing_size', retail_price=10000,
            reseller_price=8000, reseller_moq=1, is_active=True,
        )
        self.size = Size.objects.create(label='XL')
        self.variant = Variant.objects.create(product=self.product, size=self.size, stock_qty=8)
        self.customer = {
            'name':'Client test', 'phone':'690123456',
            'city':'Yaounde','quarter':'Bastos','address':'Adresse fictive',
        }

    def _order(self, number='TEST-COLOR-1', color='Blanc'):
        order = Order.objects.create(
            order_no=number, customer_name=self.customer['name'],
            customer_phone=self.customer['phone'], city='Yaounde',
            quarter='Bastos', address='Adresse fictive',
            subtotal=10000, total=13400, shipping_fee=3400,
        )
        OrderItem.objects.create(
            order=order, variant=self.variant, sku=self.product.sku,
            product_name=self.product.name, size_value='XL',
            color_name=color, unit_price=10000, qty=1, line_total=10000,
        )
        return order

    def test_checkout_saves_color_snapshot(self):
        response = self.client.post(
            '/api/checkout/',
            data=json.dumps({'customer':self.customer, 'pay_method':'MTN Mobile Money',
                             'items':[{'sku':self.product.sku, 'size':'XL','qty':1}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()['orderNo'])
        item = order.items.get()
        self.assertEqual(item.color_name, 'Blanc')
        self.product.color_name = 'Noir'
        self.product.save(update_fields=['color_name'])
        self.assertEqual(OrderItem.objects.get(pk=item.pk).color_name, 'Blanc')

    def test_admin_detail_displays_saved_color(self):
        order = self._order(color='Blanc')
        user = get_user_model().objects.create_user(
            username='admin_color_test', password='test_password', is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name='admin_orders')
        user.groups.add(group)
        self.client.force_login(user)
        response = self.client.get(f'/api/admin/order/{order.order_no}/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['order']['items'][0]['color'], 'Blanc')

    def test_existing_order_falls_back_to_product_color(self):
        order = self._order(number='TEST-COLOR-OLD', color='')
        user = get_user_model().objects.create_user(
            username='staff_color_test', password='test_password', is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name='admin_orders')
        user.groups.add(group)
        self.client.force_login(user)
        response = self.client.get(f'/api/admin/order/{order.order_no}/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['order']['items'][0]['color'], 'Blanc')

    def test_customer_tracking_displays_color(self):
        order = self._order(number='TEST-COLOR-TRACK', color='Blanc')
        response = self.client.post(
            f'/api/track/{order.order_no}/',
            data=json.dumps({'phone':self.customer['phone']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['order']['items'][0]['color'], 'Blanc')
