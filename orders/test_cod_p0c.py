"""P0-C: flux manuel COD, journalisation et annulations (DB de test Django)."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Size, Variant
from orders.models import CODCollection, Order, PaymentStatusLog
from sourcing.models import Supplier, SupplierOffer, ProcurementLine, DeliveryTask


class CODP0CTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="ekako_cod_p0c_admin", email="cod-test@example.org", password="test-long-pass-2026"
        )
        supplier = Supplier.objects.create(name="Commerce P0C fictif", status="active")
        cls.product = Product.objects.create(
            sku="P0C-TEST-001", name="T-shirt test P0-C", retail_price=10000,
            reseller_price=9000, is_active=True,
        )
        cls.size = Size.objects.create(label="P0C-TEST-M")
        cls.variant = Variant.objects.create(product=cls.product, size=cls.size, stock_qty=12)
        SupplierOffer.objects.create(product=cls.product, supplier=supplier, purchase_price=7000)

    def order(self, key):
        payload = {
            "customer": {"name": "Client P0C", "phone": "699987650", "city": "Yaounde", "quarter": "Bastos", "address": "Adresse fictive"},
            "pay_method": "Paiement a la livraison (optionnel)",
            "items": [{"sku": self.product.sku, "size": self.size.label, "qty": 1}],
        }
        r = self.client.post(reverse("checkout_api"), data=json.dumps(payload), content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(r.status_code, 200, r.content)
        return Order.objects.get(order_no=r.json()["orderNo"])

    def update_status(self, order, status):
        self.client.force_login(self.admin)
        return self.client.post(reverse("admin_update_status_api", kwargs={"order_no": order.order_no}),
                                data=json.dumps({"status": status}), content_type="application/json")

    def collect(self, order, reference, amount=None):
        self.client.force_login(self.admin)
        return self.client.post(reverse("admin_cod_collect_api", kwargs={"order_no": order.order_no}),
                                data=json.dumps({"reference": reference, "amount": amount if amount is not None else order.total}),
                                content_type="application/json")

    def paid(self, order, reference):
        self.client.force_login(self.admin)
        return self.client.post(reverse("admin_update_payment_status_api", kwargs={"order_no": order.order_no}),
                                data=json.dumps({"payment_status": "paid", "payment_ref": reference, "verified": True}),
                                content_type="application/json")

    def ship(self, order):
        line = ProcurementLine.objects.get(order_item__order=order)
        line.status = "confirmed"
        line.save()
        self.assertEqual(self.update_status(order, "preparing").status_code, 200)
        line.status = "collected"
        line.save()
        delivery = DeliveryTask.objects.get(order=order)
        delivery.courier_name = "Livreur P0C"
        delivery.status = "assigned"
        delivery.save()
        self.assertEqual(self.update_status(order, "shipped").status_code, 200)
        return delivery

    def test_new_cod_delivered_requires_receipt(self):
        order = self.order("ekako-p0c-receipt-required")
        delivery = self.ship(order)
        delivery.status = "delivered"
        delivery.save()
        self.assertEqual(self.update_status(order, "delivered").status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")

    def test_receipt_declaration_then_financial_confirmation(self):
        order = self.order("ekako-p0c-reconcile-0001")
        delivery = self.ship(order)
        self.assertEqual(self.collect(order, "CASH-P0C-0001").status_code, 200)
        self.assertEqual(CODCollection.objects.get(order=order).recorded_by, self.admin)
        delivery.status = "delivered"
        delivery.delivery_note = "Remis au client"
        delivery.save()
        self.assertEqual(self.update_status(order, "delivered").status_code, 200)
        self.assertEqual(self.paid(order, "OTHER-P0C-0001").status_code, 409)
        self.assertEqual(self.paid(order, "CASH-P0C-0001").status_code, 200)
        self.assertEqual(self.paid(order, "CASH-P0C-0001").status_code, 200)
        receipt = CODCollection.objects.get(order=order)
        self.assertEqual(receipt.verified_by, self.admin)
        self.assertIsNotNone(receipt.verified_at)
        self.assertEqual(PaymentStatusLog.objects.filter(order=order, new_state="paid").count(), 1)

    def test_refuses_incorrect_amount_and_unshipped_cash(self):
        order = self.order("ekako-p0c-invalid-00001")
        self.assertEqual(self.collect(order, "CASH-P0C-0002").status_code, 409)
        self.ship(order)
        self.assertEqual(self.collect(order, "CASH-P0C-0002", amount=1).status_code, 400)
        self.assertEqual(CODCollection.objects.filter(order=order).count(), 0)

    def test_receipt_is_idempotent_and_immutable(self):
        order = self.order("ekako-p0c-immutable-001")
        self.ship(order)
        first = self.collect(order, "CASH-P0C-0003")
        self.assertEqual(first.status_code, 200, first.content)
        replay = self.collect(order, "CASH-P0C-0003")
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json().get("idempotent"))
        self.assertEqual(self.collect(order, "CASH-P0C-CHANGED").status_code, 409)
        self.assertEqual(CODCollection.objects.filter(order=order).count(), 1)

    def test_same_receipt_reference_cannot_pay_two_orders(self):
        a = self.order("ekako-p0c-unique-ref-0001")
        b = self.order("ekako-p0c-unique-ref-0002")
        self.ship(a)
        self.ship(b)
        self.assertEqual(self.collect(a, "CASH-P0C-0004").status_code, 200)
        self.assertEqual(self.collect(b, "CASH-P0C-0004").status_code, 409)
        self.assertEqual(CODCollection.objects.count(), 1)

    def test_paid_or_collected_orders_cannot_be_cancelled_silently(self):
        order = self.order("ekako-p0c-collected-0001")
        self.ship(order)
        self.assertEqual(self.update_status(order, "cancelled").status_code, 400)  # shipped is terminal for cancellation in V1
        old = Order.objects.create(
            order_no="EKAKO-P0C-PAID-OLD", status="received", payment_state="paid",
            payment_reference="LEGACY-TEST-PAID", customer_name="Client test", customer_phone="699111222",
            city="Yaounde", quarter="Bastos", address="Adresse test", subtotal=1000, total=1000,
        )
        self.assertEqual(self.update_status(old, "cancelled").status_code, 409)
        old.refresh_from_db()
        self.assertEqual(old.status, "received")

    def test_reserved_supplier_requires_release_before_cancel(self):
        order = self.order("ekako-p0c-supplier-0001")
        line = ProcurementLine.objects.get(order_item__order=order)
        line.status = "confirmed"
        line.save()
        self.assertEqual(self.update_status(order, "cancelled").status_code, 409)
        line.status = "cancelled"  # Libération fournisseur confirmée manuellement
        line.save()
        self.assertEqual(self.update_status(order, "cancelled").status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(ProcurementLine.objects.get(order_item__order=order).status, "cancelled")
