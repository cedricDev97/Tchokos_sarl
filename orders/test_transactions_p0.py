"""Non-régression transactions eKAKO P0-A, sur base temporaire Django."""
import json
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.permissions import can_manage_orders, can_manage_payments
from catalog.models import Product, Size, Variant
from orders.models import Order, CheckoutAttempt
from sourcing.models import Supplier, SupplierOffer, ProcurementLine, DeliveryTask


class TransactionP0Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(username="ekako_p0_super", email="p0@example.org", password="test-strong-2026")
        cls.staff = get_user_model().objects.create_user(username="ekako_p0_staff", password="test-strong-2026", is_staff=True)
        cls.supplier = Supplier.objects.create(name="Fournisseur test P0", status="active")
        cls.product = Product.objects.create(sku="EKAKO-P0-001", name="Chaussures P0", retail_price=15000, reseller_price=14000, reseller_moq=1, is_active=True)
        cls.size = Size.objects.create(label="P0-43")
        cls.variant = Variant.objects.create(product=cls.product, size=cls.size, stock_qty=3)
        cls.offer = SupplierOffer.objects.create(product=cls.product, supplier=cls.supplier, purchase_price=10000, availability_state="reported")

    def payload(self, qty=1):
        return {
            "customer": {"name": "Client P0", "phone": "699005566", "city": "Yaounde", "quarter": "Bastos", "address": "Adresse test"},
            "pay_method": "Paiement a la livraison (optionnel)",
            "items": [{"sku": self.product.sku, "size": self.size.label, "qty": qty}],
        }

    def checkout(self, key, qty=1):
        return self.client.post(reverse("checkout_api"), data=json.dumps(self.payload(qty)),
                                content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)

    def update_status(self, order, status):
        self.client.force_login(self.admin)
        return self.client.post(reverse("admin_update_status_api", kwargs={"order_no": order.order_no}),
                                data=json.dumps({"status": status}), content_type="application/json")

    def test_replay_returns_same_order_and_decrements_once(self):
        a = self.checkout("ekako-p0-replay-000001")
        b = self.checkout("ekako-p0-replay-000001")
        self.assertEqual(a.status_code, 200, a.content)
        self.assertEqual(b.status_code, 200, b.content)
        self.assertEqual(a.json()["orderNo"], b.json()["orderNo"])
        self.assertTrue(b.json()["idempotent"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)
        self.assertEqual(ProcurementLine.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 2)

    def test_reusing_key_with_different_cart_rejected(self):
        a = self.checkout("ekako-p0-conflict-000001", qty=1)
        b = self.checkout("ekako-p0-conflict-000001", qty=2)
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 409)
        self.assertEqual(Order.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 2)

    @override_settings(IS_PRODUCTION=True)
    def test_production_requires_idempotency_key(self):
        r = self.client.post(reverse("checkout_api"), data=json.dumps(self.payload()), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_cannot_prepare_before_supplier_confirmation(self):
        r = self.checkout("ekako-p0-prepare-000001")
        order = Order.objects.get(order_no=r.json()["orderNo"])
        blocked = self.update_status(order, "preparing")
        self.assertEqual(blocked.status_code, 409, blocked.content)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.status, "received")

    def test_cannot_ship_until_all_collected_and_courier_assigned(self):
        r = self.checkout("ekako-p0-ship-00000001")
        order = Order.objects.get(order_no=r.json()["orderNo"])
        line = ProcurementLine.objects.get(order_item__order=order)
        line.status = "confirmed"
        line.save()
        self.assertEqual(self.update_status(order, "preparing").status_code, 200)
        self.assertEqual(self.update_status(order, "shipped").status_code, 409)
        line.status = "collected"
        line.save()
        self.assertEqual(self.update_status(order, "shipped").status_code, 409)
        delivery = DeliveryTask.objects.get(order=order)
        delivery.status = "assigned"
        delivery.courier_name = "Livreur Test P0"
        delivery.save()
        self.assertEqual(self.update_status(order, "shipped").status_code, 200)
        self.assertEqual(self.update_status(order, "delivered").status_code, 409)
        delivery.status = "delivered"
        delivery.delivery_note = "Remis au client test"
        delivery.save()

        # P0-C : livraison bloquee sans declaration d'encaissement.
        self.assertEqual(self.update_status(order, "delivered").status_code, 409)

        receipt = self.client.post(
            reverse("admin_cod_collect_api", kwargs={"order_no": order.order_no}),
            data=json.dumps({
                "amount": order.total,
                "reference": "CASH-P0A-DELIVERY-0001",
            }),
            content_type="application/json",
        )
        self.assertEqual(receipt.status_code, 200, receipt.content)

        self.assertEqual(self.update_status(order, "delivered").status_code, 200)

    def test_cancelling_from_received_restocks_once(self):
        r = self.checkout("ekako-p0-cancel-000001")
        order = Order.objects.get(order_no=r.json()["orderNo"])
        self.assertEqual(self.update_status(order, "cancelled").status_code, 200)
        self.assertEqual(self.update_status(order, "cancelled").status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 3)

    def test_plain_staff_has_no_implicit_admin_api_rights(self):
        self.assertFalse(can_manage_orders(self.staff))
        self.assertFalse(can_manage_payments(self.staff))
        self.assertTrue(can_manage_orders(self.admin))
