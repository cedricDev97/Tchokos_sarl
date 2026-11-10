"""Concurrence réelle PostgreSQL. Test DB temporaire : ne touche pas db.sqlite3.

Usage : python manage.py test orders.test_postgres_concurrency -v 2
Sur SQLite, ces tests sont délibérément ignorés (pas de row-level locking).
"""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, connections, close_old_connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from catalog.models import Product, Size, Variant
from orders.models import Order, CheckoutAttempt
from sourcing.models import DeliveryTask, ProcurementLine


@unittest.skipUnless(connection.vendor == "postgresql", "Nécessite PostgreSQL (SQLite ignore select_for_update)")
class PostgresConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.s = Size.objects.create(label="P0B-43")
        self.a = Product.objects.create(sku="P0B-A", name="Test simultané A", retail_price=15000, is_active=True)
        self.va = Variant.objects.create(product=self.a, size=self.s, stock_qty=1)
        self.customer = {
            "name": "Client PostgreSQL", "phone": "690000777", "city": "Yaounde",
            "quarter": "Bastos", "address": "Adresse de test",
        }

    def payload(self, sku="P0B-A", items=None):
        return {
            "customer": self.customer,
            "pay_method": "Paiement a la livraison (optionnel)",
            "items": items if items is not None else [{"sku": sku, "size": self.s.label, "qty": 1}],
        }

    def run_pair(self, inputs):
        """Deux connexions SQL indépendantes, départ synchronisé."""
        gate = threading.Barrier(2)

        def worker(payload, key):
            close_old_connections()
            try:
                gate.wait(timeout=15)
                resp = Client().post(
                    reverse("checkout_api"),
                    data=json.dumps(payload),
                    content_type="application/json",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
                return resp.status_code, resp.json()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker, payload, key) for payload, key in inputs]
            return [future.result(timeout=40) for future in futures]

    def test_two_distinct_checkouts_cannot_oversell_last_unit(self):
        p = self.payload()
        results = self.run_pair([(p, "P0B-distinct-aaaa1111"), (p, "P0B-distinct-bbbb2222")])
        self.assertEqual(sorted(status for status, _ in results), [200, 400], results)
        self.va.refresh_from_db()
        self.assertEqual(self.va.stock_qty, 0)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)
        self.assertEqual(ProcurementLine.objects.count(), 1)
        self.assertEqual(DeliveryTask.objects.count(), 1)

    def test_two_requests_same_key_create_one_order(self):
        p = self.payload()
        key = "P0B-replay-cccc3333"
        results = self.run_pair([(p, key), (p, key)])
        self.assertEqual(sorted(status for status, _ in results), [200, 200], results)
        self.assertEqual(results[0][1]["orderNo"], results[1][1]["orderNo"])
        self.va.refresh_from_db()
        self.assertEqual(self.va.stock_qty, 0)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)

    def test_reverse_cart_order_does_not_deadlock(self):
        self.va.stock_qty = 2
        self.va.save(update_fields=["stock_qty"])
        b = Product.objects.create(sku="P0B-B", name="Test simultané B", retail_price=12000, is_active=True)
        vb = Variant.objects.create(product=b, size=self.s, stock_qty=2)
        pa = self.payload(items=[
            {"sku": "P0B-A", "size": self.s.label, "qty": 1},
            {"sku": "P0B-B", "size": self.s.label, "qty": 1},
        ])
        pb = self.payload(items=list(reversed(pa["items"])))
        results = self.run_pair([(pa, "P0B-reverse-dddd4444"), (pb, "P0B-reverse-eeee5555")])
        self.assertEqual(sorted(status for status, _ in results), [200, 200], results)
        self.va.refresh_from_db()
        vb.refresh_from_db()
        self.assertEqual((self.va.stock_qty, vb.stock_qty), (0, 0))
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(ProcurementLine.objects.count(), 4)
