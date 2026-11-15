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

    def test_reseller_moq_counts_sizes_together_per_sku(self):
        second_size = Size.objects.create(label="TAILLE_TEST_2")
        second_variant = Variant.objects.create(
            product=self.product, size=second_size, stock_qty=3
        )
        self.client.force_login(self.reseller)
        payload = self.payload(qty=2)
        payload["items"].append({
            "sku": self.product.sku,
            "size": second_size.label,
            "qty": 2,
        })
        with self.cloudflare():
            response = self.post_order(payload, key="recette_moq_sizes_aggregate_01")
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        self.assertEqual(order.mode, "reseller")
        self.assertEqual(order.subtotal, 4 * 9000)
        self.variant.refresh_from_db()
        second_variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)
        self.assertEqual(second_variant.stock_qty, 1)

    def test_reseller_moq_never_allows_exceeding_size_stock(self):
        second_size = Size.objects.create(label="TAILLE_TEST_3")
        second_variant = Variant.objects.create(
            product=self.product, size=second_size, stock_qty=3
        )
        self.client.force_login(self.reseller)
        payload = self.payload(qty=8)
        payload["items"].append({
            "sku": self.product.sku,
            "size": second_size.label,
            "qty": 2,
        })
        with self.cloudflare():
            response = self.post_order(payload, key="recette_stock_variant_oversell_01")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.variant.refresh_from_db()
        second_variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 7)
        self.assertEqual(second_variant.stock_qty, 3)

    def test_invalid_cameroon_phone_is_rejected_without_stock_change(self):
        for index, invalid in enumerate(("6543-2023", "123456789", "69900112", "6990011220", "69900A122")):
            with self.subTest(phone=invalid), self.cloudflare():
                payload = self.payload()
                payload["customer"]["phone"] = invalid
                response = self.post_order(payload, key=f"recette_bad_phone_{index:02d}_00001")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("Téléphone camerounais", response.json()["error"])
                self.assert_untouched()

    def test_phone_with_country_prefix_is_normalized_and_trackable(self):
        payload = self.payload()
        payload["customer"]["phone"] = "+237 699 00 11 22"
        with self.cloudflare():
            response = self.post_order(payload, key="recette_phone_prefix_valid_001")
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        self.assertEqual(order.customer_phone, "699001122")
        self.assertEqual(order.payment_state, "unpaid")
        self.assertEqual(response.json()["payment_status"], "unpaid")
        lookup = self.client.post(
            reverse("track_api", kwargs={"order_no": order.order_no}),
            data=json.dumps({"phone": "699 00 11 22"}),
            content_type="application/json",
        )
        self.assertEqual(lookup.status_code, 200, lookup.content)
        self.assertEqual(lookup.json()["order"]["payment_status"], "unpaid")

    @override_settings(EKAKO_CHECKOUT_MODE="closed")
    def test_checkout_closed_does_not_create_order(self):
        response = self.post_order(self.payload(), key="recette_closed_checkout_0001")
        self.assertEqual(response.status_code, 503, response.content)
        self.assert_untouched()

    @override_settings(IS_PRODUCTION=True, EKAKO_CHECKOUT_MODE="sandbox")
    def test_production_never_accepts_sandbox_checkout(self):
        response = self.post_order(self.payload(), key="recette_prod_guard_0000001")
        self.assertEqual(response.status_code, 503, response.content)
        self.assert_untouched()

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
