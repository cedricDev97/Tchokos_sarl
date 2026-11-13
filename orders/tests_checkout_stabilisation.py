"""Tests isolés du checkout eKAKO V1 : aucun stock ni commande réelle modifiés.

Exécution :
    python3 manage.py test orders.tests_checkout_stabilisation
"""
import json
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Product, Size, Variant
from orders.models import CheckoutAttempt, Order
from orders.views import compute_shipping


@override_settings(
    EKAKO_MAINTENANCE=False,
    EKAKO_TURNSTILE_ENABLED=True,
    EKAKO_TURNSTILE_SITE_KEY="checkout-test-site",
    EKAKO_TURNSTILE_SECRET_KEY="checkout-test-secret",
    EKAKO_TURNSTILE_HOSTNAME="ekako.test",
)
class CheckoutStabilisationTests(TestCase):
    """Chaque test utilise la base temporaire créée puis détruite par Django."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            sku="EKAKO-CHECKOUT-TEST",
            name="Article de recette",
            category="Vêtements",
            retail_price=12000,
            reseller_price=9000,
            reseller_moq=4,
            variant_type="clothing_size",
            is_active=True,
        )
        cls.size = Size.objects.create(label="TAILLE_TEST")
        cls.variant = Variant.objects.create(
            product=cls.product, size=cls.size, stock_qty=7
        )
        cls.reseller = get_user_model().objects.create_user(
            username="test_reseller_checkout",
            password="SecureTestPassword123!",
        )
        group, _ = Group.objects.get_or_create(name="reseller")
        cls.reseller.groups.add(group)

    def payload(self, qty=2):
        return {
            "customer": {
                "name": "Client de recette",
                "phone": "699001122",
                "city": "Yaounde",
                "quarter": "Bastos",
                "address": "Adresse fictive",
            },
            "items": [{
                "sku": self.product.sku,
                "size": self.size.label,
                "qty": qty,
            }],
            "pay_method": "MTN Mobile Money",
        }

    def post_order(self, payload, key="recette_checkout_unique_key_0001", token="dummy-token"):
        return self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_EKAKO_TURNSTILE=token,
        )

    def cloudflare(self, *, success=True, action="checkout", hostname="ekako.test"):
        # Le mock évite tout appel réel à Cloudflare.
        result = {"success": success, "action": action, "hostname": hostname}
        wire = json.dumps(result).encode("utf-8")
        return patch(
            "config.turnstile.http_request.urlopen",
            side_effect=lambda *args, **kwargs: BytesIO(wire),
        )

    def assert_untouched(self):
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 7)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CheckoutAttempt.objects.count(), 0)

    def test_captcha_missing_rejected_before_order(self):
        response = self.post_order(self.payload(), token="")
        self.assertEqual(response.status_code, 400)
        self.assert_untouched()

    def test_captcha_failed_rejected_before_order(self):
        with self.cloudflare(success=False):
            response = self.post_order(self.payload())
        self.assertEqual(response.status_code, 400)
        self.assert_untouched()

    def test_captcha_other_action_rejected_before_order(self):
        with self.cloudflare(action="login"):
            response = self.post_order(self.payload())
        self.assertEqual(response.status_code, 400)
        self.assert_untouched()

    def test_captcha_other_domain_rejected_before_order(self):
        with self.cloudflare(hostname="unknown.test"):
            response = self.post_order(self.payload())
        self.assertEqual(response.status_code, 400)
        self.assert_untouched()

    def test_captcha_network_failure_does_not_create_order(self):
        with patch(
            "config.turnstile.http_request.urlopen",
            side_effect=OSError("service temporarily offline"),
        ):
            response = self.post_order(self.payload())
        self.assertEqual(response.status_code, 503)
        self.assert_untouched()

    def test_valid_checkout_uses_server_prices_and_shipping(self):
        data = self.payload(qty=2)
        # Les champs envoyés par le navigateur ne doivent pas décider du tarif.
        data.update({"role": "reseller", "mode": "reseller", "shipping_fee": 0})
        with self.cloudflare():
            response = self.post_order(data)
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        self.assertEqual(order.mode, "retail")
        self.assertEqual(order.subtotal, 24000)
        self.assertEqual(order.shipping_fee, compute_shipping("Yaounde", "Bastos"))
        self.assertEqual(order.total, order.subtotal + order.shipping_fee)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)

    def test_identical_retry_returns_same_order_and_decrements_once(self):
        payload = self.payload(qty=2)
        key = "recette_retry_same_key_00000001"
        with self.cloudflare():
            first = self.post_order(payload, key=key, token="first-token")
            second = self.post_order(payload, key=key, token="second-token")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["orderNo"], second.json()["orderNo"])
        self.assertTrue(second.json()["idempotent"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)

    def test_same_key_different_cart_is_rejected(self):
        key = "recette_same_key_new_cart_0001"
        with self.cloudflare():
            first = self.post_order(self.payload(qty=2), key=key)
            second = self.post_order(self.payload(qty=3), key=key)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(Order.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)

    def test_reseller_minimum_enforced_by_server(self):
        self.client.force_login(self.reseller)
        with self.cloudflare():
            below_minimum = self.post_order(self.payload(qty=3), key="recette_moq_below_minimum_001")
            valid = self.post_order(self.payload(qty=4), key="recette_moq_reached_minimum_001")
        self.assertEqual(below_minimum.status_code, 400, below_minimum.content)
        self.assertEqual(valid.status_code, 200, valid.content)
        order = Order.objects.get(order_no=valid.json()["orderNo"])
        self.assertEqual(order.mode, "reseller")
        self.assertEqual(order.subtotal, 36000)
        self.assertEqual(Order.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 3)

    def test_insufficient_stock_rejected(self):
        with self.cloudflare():
            response = self.post_order(self.payload(qty=8))
        self.assertEqual(response.status_code, 400)
        self.assert_untouched()

    def test_post_without_csrf_cookie_is_rejected(self):
        # Une seconde instance de Client impose réellement la protection CSRF.
        strict = Client(enforce_csrf_checks=True)
        response = strict.post(
            reverse("checkout_api"),
            data=json.dumps(self.payload()),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="recette_missing_csrf_001",
        )
        self.assertEqual(response.status_code, 403)
        self.assert_untouched()
