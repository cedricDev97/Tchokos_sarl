"""Régression eKAKO : intégrité des stocks et transitions de commandes.
Ces tests utilisent une base temporaire créée par Django (pas db.sqlite3).
"""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Size, Variant
from orders.models import Order, OrderItem, OrderStatusLog


class StockIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            sku="TK-TEST-001", name="Article test eKAKO", category="Textile",
            retail_price=10000, reseller_price=8000, reseller_moq=5,
            color_name="Blanc",
            variant_type="clothing_size", is_active=True,
        )
        cls.size = Size.objects.create(label="EKAKO-TEST-M")
        cls.variant = Variant.objects.create(product=cls.product, size=cls.size, stock_qty=5)
        cls.admin = get_user_model().objects.create_superuser(
            username="ekako_test_stock_admin", email="admin-test@example.com", password="test-password-long"
        )

    def post_checkout(self, items, **overrides):
        payload = {
            "customer": {"name": "Client Test", "phone": "699001122", "city": "Yaounde",
                         "quarter": "Bastos", "address": "Adresse de test"},
            "pay_method": "MTN Mobile Money", "items": items,
        }
        payload.update(overrides)
        return self.client.post(reverse("checkout_api"), data=json.dumps(payload), content_type="application/json")

    def line(self, qty):
        return {"sku": self.product.sku, "size": self.size.label, "qty": qty}

    def test_identical_rows_cannot_exceed_stock(self):
        response = self.post_checkout([self.line(3), self.line(3)])
        self.assertEqual(response.status_code, 400)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_identical_rows_aggregated_and_stock_once(self):
        response = self.post_checkout([self.line(2), self.line(1)])
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        self.assertEqual(order.subtotal, 30000)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().qty, 3)
        self.assertEqual(order.items.first().color_name, "Blanc")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 2)

    def test_malformed_request_does_not_create_order(self):
        response = self.client.post(reverse("checkout_api"), data="{wrong",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response2 = self.post_checkout([self.line("not-a-number")])
        self.assertEqual(response2.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_product_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        response = self.post_checkout([self.line(1)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_reseller_moq_checked_on_total(self):
        reseller = get_user_model().objects.create_user(
            username="ekako_reseller_stock_test", password="test-password-long"
        )
        group, _ = Group.objects.get_or_create(name="reseller")
        reseller.groups.add(group)
        self.client.force_login(reseller)
        response = self.post_checkout([self.line(2), self.line(2)])
        self.assertEqual(response.status_code, 400)
        response2 = self.post_checkout([self.line(3), self.line(2)])
        self.assertEqual(response2.status_code, 200)
        order = Order.objects.get(order_no=response2.json()["orderNo"])
        self.assertEqual(order.subtotal, 40000)
        self.assertEqual(order.items.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 0)

    def test_cancel_restores_exactly_once(self):
        response = self.post_checkout([self.line(2)])
        self.assertEqual(response.status_code, 200)
        order_no = response.json()["orderNo"]
        self.client.force_login(self.admin)
        url = reverse("admin_update_status_api", kwargs={"order_no": order_no})
        def cancel():
            return self.client.post(url, data=json.dumps({"status": "cancelled"}),
                                    content_type="application/json")
        self.assertEqual(cancel().status_code, 200)
        self.assertEqual(cancel().status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)
        self.assertEqual(OrderStatusLog.objects.filter(order__order_no=order_no).count(), 1)
        self.assertEqual(Order.objects.get(order_no=order_no).status, "cancelled")
