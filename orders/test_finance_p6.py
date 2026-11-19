from django.test import TestCase, override_settings
from catalog.models import Product, Size, Variant
from orders.models import Order, OrderItem, OrderCostSheet
from orders.finance import order_finance_summary
from sourcing.models import Supplier, ProcurementLine


class FinanceP6Tests(TestCase):

    @classmethod
    def setUpTestData(cls):
        product = Product.objects.create(
            sku="EK-FIN-P6",
            name="Article financier fictif",
            category="Textile",
            retail_price=15000,
            reseller_price=12000,
            reseller_moq=1,
            is_active=True,
        )
        size = Size.objects.create(label="FIN-P6-M")
        variant = Variant.objects.create(
            product=product, size=size, stock_qty=10
        )
        cls.order = Order.objects.create(
            order_no="EKAKOFINP6",
            customer_name="Client fictif",
            customer_phone="699001122",
            city="Yaounde",
            quarter="Bastos",
            address="Test",
            subtotal=30000,
            shipping_fee=3400,
            total=33400,
        )
        cls.item = OrderItem.objects.create(
            order=cls.order,
            variant=variant,
            sku=product.sku,
            product_name=product.name,
            size_value=size.label,
            unit_price=15000,
            qty=2,
            line_total=30000,
        )

    def test_couts_incomplets(self):
        summary = order_finance_summary(self.order)
        self.assertIsNone(summary["margin_contribution"])
        self.assertEqual(summary["status"], "incomplete")
        self.assertFalse(summary["ready_for_closing"])

    def test_marge_complete(self):
        supplier = Supplier.objects.create(
            name="Fournisseur fictif P6",
            status="active",
        )
        ProcurementLine.objects.create(
            order_item=self.item,
            supplier=supplier,
            unit_cost=9000,
            status="confirmed",
        )
        OrderCostSheet.objects.create(
            order=self.order,
            courier_cost=2200,
            payment_fee=350,
            other_cost=250,
        )

        summary = order_finance_summary(self.order)
        self.assertEqual(summary["supplier_cost"], 18000)
        self.assertEqual(summary["order_total"], 33400)
        self.assertEqual(summary["margin_contribution"], 12600)
        self.assertEqual(summary["status"], "provisional")
        self.assertFalse(summary["ready_for_closing"])
        self.assertFalse(
            summary["reconciliation"]["external_cash_reconciled"]
        )
