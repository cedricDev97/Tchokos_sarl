"""Tests modèle B : DB Django temporaire, jamais la base locale db.sqlite3."""
import json
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Size, Variant
from orders.models import Order
from sourcing.models import Supplier, SupplierOffer, ProcurementLine, SupplierPayment, DeliveryTask


class ModelBTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier = Supplier.objects.create(
            name="Commerce test Bastos", city="Yaounde", quarter="Bastos", status="active",
            pickup_address="Adresse fictive de collecte",
        )
        cls.product = Product.objects.create(
            sku="TEST-MB-ROUGE", name="Jogging test rouge", color_name="Rouge",
            variant_type="clothing_size", retail_price=25000, reseller_price=22000,
            reseller_moq=1, is_active=True,
        )
        cls.size = Size.objects.create(label="EKAKO-MB-L")
        cls.variant = Variant.objects.create(product=cls.product, size=cls.size, stock_qty=9)
        cls.offer = SupplierOffer.objects.create(
            product=cls.product, supplier=cls.supplier, purchase_price=20000,
            availability_state="reported",
        )
        cls.customer = {
            "name": "Client Test", "phone": "699987654", "city": "Yaounde",
            "quarter": "Bastos", "address": "Adresse fictive",
        }

    def order(self, sku=None, qty=1):
        payload = {
            "customer": self.customer, "pay_method": "MTN Mobile Money",
            "items": [{"sku": sku or self.product.sku, "size": self.size.label, "qty": qty}],
        }
        resp = self.client.post(reverse("checkout_api"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)
        return Order.objects.get(order_no=resp.json()["orderNo"])

    def test_supplier_offer_and_margin_snapshot_on_checkout(self):
        order = self.order(qty=2)
        line = ProcurementLine.objects.get(order_item__order=order)
        self.assertEqual(line.status, "to_confirm")
        self.assertEqual(line.supplier, self.supplier)
        self.assertEqual(line.unit_cost, 20000)
        self.assertEqual(line.cost_total, 40000)
        self.assertEqual(line.gross_margin, 10000)
        self.assertEqual(line.order_item.color_name, "Rouge")
        self.assertEqual(DeliveryTask.objects.get(order=order).status, "planned")
        self.offer.purchase_price = 23000
        self.offer.save(update_fields=["purchase_price"])
        line.refresh_from_db()
        self.assertEqual(line.unit_cost, 20000)

    def test_unknown_supplier_and_cost_do_not_invent_a_margin(self):
        other = Product.objects.create(sku="TEST-MB-UNKNOWN", name="Produit sans commerçant", retail_price=3000, is_active=True)
        Variant.objects.create(product=other, size=self.size, stock_qty=4)
        order = self.order(sku=other.sku)
        line = ProcurementLine.objects.get(order_item__order=order)
        self.assertEqual(line.status, "unassigned")
        self.assertIsNone(line.supplier)
        self.assertIsNone(line.unit_cost)
        self.assertIsNone(line.gross_margin)
        self.assertIsNone(line.payable_balance)

    def test_supplier_payment_balance_is_only_manual_ledger(self):
        order = self.order(qty=2)
        line = ProcurementLine.objects.get(order_item__order=order)
        SupplierPayment.objects.create(procurement=line, amount=10000, method="cash", reference="TEST-CASH-01")
        self.assertEqual(line.payable_balance, 30000)
        too_much = SupplierPayment(procurement=line, amount=30001, method="cash")
        with self.assertRaises(ValidationError):
            too_much.full_clean()

    def test_no_supplier_cannot_confirm_sourcing(self):
        p = Product.objects.create(sku="TEST-MB-MISSING", name="Sans partenaire", retail_price=1500)
        Variant.objects.create(product=p, size=self.size, stock_qty=3)
        order = self.order(sku=p.sku)
        line = ProcurementLine.objects.get(order_item__order=order)
        line.status = "confirmed"
        with self.assertRaises(ValidationError):
            line.full_clean()

    def test_preexisting_order_is_not_backfilled(self):
        from orders.models import OrderItem
        older = Order.objects.create(order_no="TEST-MB-LEGACY", customer_name="Client test", customer_phone="699111222",
            city="Yaounde", quarter="Bastos", address="Adresse test", subtotal=25000, total=25000)
        OrderItem.objects.create(order=older, variant=self.variant, sku=self.product.sku,
            product_name=self.product.name, size_value=self.size.label, color_name="Rouge", qty=1,
            unit_price=25000, line_total=25000)
        self.assertFalse(ProcurementLine.objects.filter(order_item__order=older).exists())
        self.assertFalse(DeliveryTask.objects.filter(order=older).exists())

    def test_second_supplier_separate_lines_single_delivery(self):
        other_supplier = Supplier.objects.create(name="Commerce test Emana", status="active")
        second = Product.objects.create(sku="TEST-MB-BLANC", name="Jogging blanc", retail_price=10000, is_active=True)
        Variant.objects.create(product=second, size=self.size, stock_qty=2)
        SupplierOffer.objects.create(product=second, supplier=other_supplier, purchase_price=7000)
        payload = {"customer": self.customer, "pay_method": "Orange Money", "items": [
            {"sku": self.product.sku, "size": self.size.label, "qty": 1},
            {"sku": second.sku, "size": self.size.label, "qty": 1},
        ]}
        r = self.client.post(reverse("checkout_api"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        o = Order.objects.get(order_no=r.json()["orderNo"])
        self.assertEqual(ProcurementLine.objects.filter(order_item__order=o).count(), 2)
        self.assertEqual(ProcurementLine.objects.filter(order_item__order=o).aggregate(total=Sum("unit_cost"))["total"], 27000)
        self.assertEqual(DeliveryTask.objects.filter(order=o).count(), 1)
