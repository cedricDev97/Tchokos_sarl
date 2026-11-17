"""Sécurisation P2 du suivi de commande, DB temporaire et sans réseau."""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import LoginAttemptCounter
from orders.models import Order


@override_settings(EKAKO_MAINTENANCE=False)
class OrderTrackingThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = Order.objects.create(
            order_no="EKAKO12345678", customer_name="Client de test",
            customer_phone="699001122", city="Yaounde", quarter="Bastos",
            address="Adresse test", subtotal=15000, total=15000,
            pay_method="MTN Mobile Money",
        )

    def lookup(self, order_no="EKAKO12345678", phone="699888777", ip="192.0.2.10"):
        return self.client.post(
            f"/api/track/{order_no}/",
            data=json.dumps({"phone": phone}),
            content_type="application/json",
            REMOTE_ADDR=ip,
        )

    def test_fifth_failure_blocks_correct_sixth_attempt(self):
        for _ in range(5):
            self.assertEqual(self.lookup().status_code, 404)
        response = self.lookup(phone="699001122")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertNotIn("EKAKO12345678", response.content.decode())

    def test_unknown_orders_count_and_share_ip_budget(self):
        for n in range(20):
            response = self.lookup(order_no=f"EKAKO{n:08d}")
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.lookup(phone="699001122").status_code, 429)

    def test_successful_lookup_preserves_tracking_and_resets_pair(self):
        self.assertEqual(self.lookup().status_code, 404)
        success = self.lookup(phone="+237 699 00 11 22")
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["order"]["orderNo"], self.order.order_no)
        self.assertEqual(self.lookup().status_code, 404)

    def test_other_ip_has_independent_pair_budget(self):
        for _ in range(5):
            self.assertEqual(self.lookup().status_code, 404)
        self.assertEqual(self.lookup(phone="699001122", ip="192.0.2.11").status_code, 200)

    def test_expired_counters_stop_blocking(self):
        for _ in range(5):
            self.lookup()
        self.assertEqual(self.lookup(phone="699001122").status_code, 429)
        LoginAttemptCounter.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.lookup(phone="699001122").status_code, 200)

    def test_invalid_short_phone_is_counted(self):
        for _ in range(5):
            self.assertEqual(self.lookup(phone="123").status_code, 400)
        self.assertEqual(self.lookup(phone="699001122").status_code, 429)

    def test_login_and_tracking_counters_are_isolated(self):
        from accounts.login_throttle import record_failed_login, login_retry_after
        request = type("FakeRequest", (), {"META": {"REMOTE_ADDR": "192.0.2.10"}})()
        record_failed_login(request, "dummy")
        self.assertEqual(login_retry_after(request, "dummy"), 0)
        self.assertEqual(self.lookup(phone="699001122").status_code, 200)

    def test_no_database_or_stock_mutation(self):
        original_total = self.order.total
        for _ in range(5):
            self.lookup()
        self.order.refresh_from_db()
        self.assertEqual(self.order.total, original_total)
        self.assertEqual(Order.objects.count(), 1)
