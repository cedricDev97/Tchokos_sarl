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

    def test_legacy_tk_order_remains_trackable(self):
        """La migration de marque ne renumérote pas les anciennes commandes."""
        legacy = Order.objects.create(
            order_no="TK12345678",
            customer_name="Ancien client",
            customer_phone="699001122",
            city="Yaounde",
            quarter="Bastos",
            address="Adresse historique",
            subtotal=12000,
            shipping_fee=3400,
            total=15400,
            pay_method="MTN Mobile Money",
        )
        response = self.client.post(
            reverse("track_api", kwargs={"order_no": legacy.order_no}),
            data=json.dumps({"phone": "+237 699 00 11 22"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["order"]["orderNo"], "TK12345678")

    def test_valid_checkout_uses_server_prices_and_shipping(self):
        data = self.payload(qty=2)
        # Les champs envoyés par le navigateur ne doivent pas décider du tarif.
        data.update({"role": "reseller", "mode": "reseller", "shipping_fee": 0})
        with self.cloudflare():
            response = self.post_order(data)
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        self.assertRegex(order.order_no, r"^EKAKO[0-9A-F]{8}$")
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


    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_whatsapp_checkout_reserves_stock_and_generates_prefilled_link(self):
        from urllib.parse import parse_qs, urlparse
        payload = self.payload(qty=2)
        with self.cloudflare():
            response = self.post_order(payload, key="recette_wa_order_000000001")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["checkout_channel"], "whatsapp")
        self.assertEqual(data["payment_status"], "unpaid")
        self.assertIsNotNone(data["reservation_expires_at"])
        order = Order.objects.get(order_no=data["orderNo"])
        self.assertRegex(order.order_no, r"^EKAKO[0-9A-F]{8}$")
        self.assertEqual(order.pay_method, "A confirmer sur WhatsApp")
        self.assertEqual(order.payment_state, "unpaid")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)
        url = urlparse(data["whatsapp_url"])
        self.assertEqual(url.netloc, "wa.me")
        self.assertEqual(url.path, "/237699001122")
        message = parse_qs(url.query)["text"][0]
        self.assertIn(order.order_no, message)
        self.assertIn("24,000 FCFA", message)
        self.assertNotIn("699001122", message)

    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_whatsapp_retry_does_not_deduct_stock_twice(self):
        with self.cloudflare():
            first = self.post_order(self.payload(), key="recette_wa_replay_0000001")
            second = self.post_order(self.payload(), key="recette_wa_replay_0000001")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["orderNo"], second.json()["orderNo"])
        self.assertEqual(first.json()["whatsapp_url"], second.json()["whatsapp_url"])
        self.assertTrue(second.json()["idempotent"])
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 5)
        self.assertEqual(Order.objects.count(), 1)

    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="")
    def test_whatsapp_missing_business_number_is_rejected(self):
        response = self.post_order(self.payload(), key="recette_wa_no_number_000001")
        self.assertEqual(response.status_code, 503)
        self.assert_untouched()

    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_expiration_restocks_once_and_closes_unpaid_order(self):
        from django.utils import timezone
        from django.core.management import call_command
        from datetime import timedelta
        with self.cloudflare():
            response = self.post_order(self.payload(), key="recette_wa_expire_00000001")
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_no=response.json()["orderNo"])
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])
        call_command("expire_whatsapp_reservations")
        call_command("expire_whatsapp_reservations")
        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.variant.stock_qty, 7)
        # L'expiration doit refuser toute relecture de la même clé sans dépendre
        # d'un appel réseau réel à Turnstile (toutes les requêtes du test sont mockées).
        with self.cloudflare():
            replay = self.post_order(self.payload(), key="recette_wa_expire_00000001")
        self.assertEqual(replay.status_code, 409, replay.content)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 7)

    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_tracking_recovers_whatsapp_link_after_page_closed(self):
        with self.cloudflare():
            response = self.post_order(self.payload(), key="recette_wa_track_recover_001")
        self.assertEqual(response.status_code, 200, response.content)
        order_no = response.json()["orderNo"]
        recovered = self.client.post(
            reverse("track_api", kwargs={"order_no": order_no}),
            data=json.dumps({"phone": "+237 699 00 11 22"}),
            content_type="application/json",
        )
        self.assertEqual(recovered.status_code, 200, recovered.content)
        self.assertEqual(recovered.json()["order"]["whatsapp_url"], response.json()["whatsapp_url"])
        wrong_phone = self.client.post(
            reverse("track_api", kwargs={"order_no": order_no}),
            data=json.dumps({"phone": "699111222"}),
            content_type="application/json",
        )
        self.assertEqual(wrong_phone.status_code, 404)
        self.assertNotIn("whatsapp_url", wrong_phone.json())


    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_whatsapp_manual_payment_choice_requires_privileged_confirmation(self):
        from orders.models import PaymentStatusLog
        with self.cloudflare():
            response = self.post_order(self.payload(), key="recette_wa_manual_pay_00001")
        self.assertEqual(response.status_code, 200, response.content)
        no = response.json()["orderNo"]
        endpoint = reverse("admin_confirm_whatsapp_payment_method_api", kwargs={"order_no": no})
        data = {"pay_method": "MTN Mobile Money", "confirmed_with_customer": True}

        anonymous = self.client.post(endpoint, json.dumps(data), content_type="application/json")
        self.assertNotEqual(anonymous.status_code, 200)
        self.client.force_login(self.reseller)
        forbidden = self.client.post(endpoint, json.dumps(data), content_type="application/json")
        self.assertNotEqual(forbidden.status_code, 200)

        admin = get_user_model().objects.create_superuser(
            username="ekako_wa_admin_test", password="SafePass123!zzz", email="admin@example.test"
        )
        self.client.force_login(admin)
        unconfirmed = self.client.post(endpoint,
            json.dumps({"pay_method":"MTN Mobile Money","confirmed_with_customer":False}),
            content_type="application/json")
        self.assertEqual(unconfirmed.status_code, 400)
        confirmed = self.client.post(endpoint, json.dumps(data), content_type="application/json")
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        order = Order.objects.get(order_no=no)
        self.assertEqual(order.pay_method, "MTN Mobile Money")
        self.assertEqual(order.payment_state, "unpaid")
        self.assertEqual(PaymentStatusLog.objects.filter(order=order).count(), 1)
        again = self.client.post(endpoint, json.dumps(data), content_type="application/json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(PaymentStatusLog.objects.filter(order=order).count(), 1)
        changed = self.client.post(endpoint, json.dumps({
            "pay_method":"Orange Money","confirmed_with_customer":True
        }), content_type="application/json")
        self.assertEqual(changed.status_code, 409)

    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_whatsapp_payment_must_not_be_manually_marked_paid_before_method_choice(self):
        with self.cloudflare():
            response = self.post_order(self.payload(), key="recette_wa_no_direct_paid_01")
        self.assertEqual(response.status_code, 200, response.content)
        no = response.json()["orderNo"]
        admin = get_user_model().objects.create_superuser(
            username="ekako_wa_paid_admin_test", password="SafePass123!zzz", email="admin2@example.test"
        )
        self.client.force_login(admin)
        payment = self.client.post(
            reverse("admin_update_payment_status_api", kwargs={"order_no": no}),
            json.dumps({"payment_status":"paid","payment_ref":"MTN-12345678","verified":True}),
            content_type="application/json"
        )
        self.assertEqual(payment.status_code, 409, payment.content)
        order = Order.objects.get(order_no=no)
        self.assertEqual(order.payment_state, "unpaid")


    @override_settings(EKAKO_CHECKOUT_MODE="whatsapp", EKAKO_WHATSAPP_NUMBER="237699001122", EKAKO_WHATSAPP_RESERVATION_MINUTES=60)
    def test_admin_detail_exposes_whatsapp_channel_and_reservation(self):
        """Le Dashboard doit recevoir les champs utilises par son selecteur de paiement."""
        with self.cloudflare():
            created = self.post_order(self.payload(), key="recette_wa_admin_detail_001")
        self.assertEqual(created.status_code, 200, created.content)
        no = created.json()["orderNo"]
        detail_url = reverse("admin_order_detail_api", kwargs={"order_no": no})
        self.client.force_login(self.reseller)
        forbidden = self.client.get(detail_url)
        self.assertNotEqual(forbidden.status_code, 200)
        admin = get_user_model().objects.create_superuser(
            username="ekako_whatsapp_detail_admin",
            email="detail@example.test",
            password="SafePass123!zzz",
        )
        self.client.force_login(admin)
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200, detail.content)
        order = detail.json()["order"]
        self.assertEqual(order["orderNo"], no)
        self.assertEqual(order["checkout_channel"], "whatsapp")
        self.assertEqual(order["pay_method"], "A confirmer sur WhatsApp")
        self.assertEqual(order["payment_status"], "unpaid")
        self.assertEqual(order["reservation_expires_at"], created.json()["reservation_expires_at"])


    @override_settings(
        EKAKO_CHECKOUT_MODE="whatsapp",
        EKAKO_WHATSAPP_NUMBER="237699001122",
        EKAKO_WHATSAPP_RESERVATION_MINUTES=60,
    )
    def test_whatsapp_confirmed_payment_cannot_be_recorded_twice_or_downgraded(self):
        """Même référence = réponse idempotente ; autre référence/état = refus."""
        from orders.models import PaymentStatusLog
        with self.cloudflare():
            created = self.post_order(self.payload(), key="recette_wa_paid_replay_0001")
        self.assertEqual(created.status_code, 200, created.content)
        number = created.json()["orderNo"]
        admin = get_user_model().objects.create_superuser(
            username="ekako_test_paid_replay_admin",
            email="paid-replay@example.test",
            password="SafePass123!zzz",
        )
        self.client.force_login(admin)
        choose_url = reverse(
            "admin_confirm_whatsapp_payment_method_api",
            kwargs={"order_no": number},
        )
        choose = self.client.post(
            choose_url,
            data=json.dumps({
                "pay_method": "MTN Mobile Money",
                "confirmed_with_customer": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(choose.status_code, 200, choose.content)

        payment_url = reverse(
            "admin_update_payment_status_api",
            kwargs={"order_no": number},
        )
        paid_payload = {
            "payment_status": "paid",
            "payment_ref": "RECETTE-MTN-12345678",
            "verified": True,
        }
        paid = self.client.post(
            payment_url, data=json.dumps(paid_payload), content_type="application/json"
        )
        self.assertEqual(paid.status_code, 200, paid.content)
        order = Order.objects.get(order_no=number)
        self.assertEqual(order.payment_state, "paid")
        self.assertIsNone(order.reservation_expires_at)
        self.assertIsNotNone(order.paid_at)
        first_paid_at = order.paid_at
        first_count = PaymentStatusLog.objects.filter(order=order).count()

        replay = self.client.post(
            payment_url, data=json.dumps(paid_payload), content_type="application/json"
        )
        self.assertEqual(replay.status_code, 200, replay.content)
        order.refresh_from_db()
        self.assertEqual(order.paid_at, first_paid_at)
        self.assertEqual(PaymentStatusLog.objects.filter(order=order).count(), first_count)

        for attempted in (
            {"payment_status": "paid", "payment_ref": "RECETTE-MTN-OTHER", "verified": True},
            {"payment_status": "pending", "payment_ref": "", "verified": False},
            {"payment_status": "failed", "payment_ref": "", "verified": False},
        ):
            with self.subTest(attempted=attempted):
                forbidden = self.client.post(
                    payment_url, data=json.dumps(attempted), content_type="application/json"
                )
                self.assertEqual(forbidden.status_code, 409, forbidden.content)
                order.refresh_from_db()
                self.assertEqual(order.payment_state, "paid")
                self.assertEqual(order.payment_reference, "RECETTE-MTN-12345678")
                self.assertEqual(PaymentStatusLog.objects.filter(order=order).count(), first_count)


    @override_settings(
        EKAKO_CHECKOUT_MODE="whatsapp",
        EKAKO_WHATSAPP_NUMBER="237699001122",
    )
    def test_finance_never_conflates_missing_costs_with_zero(self):
        """La marge contributive reste inconnue tant que les frais ne sont pas renseignés."""
        from sourcing.models import Supplier, ProcurementLine
        from orders.models import OrderCostSheet, OrderCostRevision

        with self.cloudflare():
            response = self.post_order(self.payload(), key="recette_finance_test_case_0001")
        self.assertEqual(response.status_code, 200, response.content)
        number = response.json()["orderNo"]
        finance_url = reverse("admin_order_finance_api", kwargs={"order_no": number})
        self.client.force_login(self.reseller)
        self.assertNotEqual(self.client.get(finance_url).status_code, 200)

        admin = get_user_model().objects.create_superuser(
            username="ekako_finance_test_admin", email="finance@example.test",
            password="SafePass123!zzz",
        )
        self.client.force_login(admin)
        first = self.client.get(finance_url)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertIsNone(first.json()["finance"]["margin_contribution"])
        self.assertEqual(first.json()["finance"]["status"], "incomplete")

        incomplete = self.client.post(
            finance_url,
            data=json.dumps({"courier_cost": 0, "payment_fee": 0, "reason": "Test sans frais manquant"}),
            content_type="application/json",
        )
        self.assertEqual(incomplete.status_code, 400)
        invalid = self.client.post(
            finance_url,
            data=json.dumps({"courier_cost": -5, "payment_fee": 0, "other_cost": 0, "reason": "Montant invalide"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)

        saved = self.client.post(
            finance_url,
            data=json.dumps({"courier_cost": 2500, "payment_fee": 150,
                             "other_cost": 0, "reason": "Test initial contrôlé"}),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()["finance"]["costs"]["other_cost"], 0)
        self.assertIsNone(saved.json()["finance"]["margin_contribution"])
        self.assertEqual(OrderCostSheet.objects.count(), 1)
        self.assertEqual(OrderCostRevision.objects.count(), 1)

        line = ProcurementLine.objects.get(order_item__order__order_no=number)
        supplier = Supplier.objects.create(name="Fournisseur recette marge", status="active")
        line.supplier = supplier
        line.unit_cost = 7000
        line.status = "confirmed"
        line.save()

        finance = self.client.get(finance_url).json()["finance"]
        self.assertEqual(finance["supplier_cost"], 14000)
        self.assertEqual(finance["gross_product_margin"], 10000)
        self.assertEqual(
            finance["margin_contribution"],
            finance["order_total"] - 14000 - 2500 - 150,
        )
        self.assertEqual(finance["status"], "provisional")

        replay = self.client.post(
            finance_url,
            data=json.dumps({"courier_cost": 2500, "payment_fee": 150,
                             "other_cost": 0, "reason": "Test initial contrôlé"}),
            content_type="application/json",
        )
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(OrderCostRevision.objects.count(), 1)

        correction = self.client.post(
            finance_url,
            data=json.dumps({"courier_cost": 2600, "payment_fee": 150,
                             "other_cost": 0, "reason": "Correction justifiée"}),
            content_type="application/json",
        )
        self.assertEqual(correction.status_code, 200, correction.content)
        self.assertEqual(OrderCostRevision.objects.count(), 2)
        self.assertEqual(OrderCostRevision.objects.first().previous_values["courier_cost"], 2500)

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
