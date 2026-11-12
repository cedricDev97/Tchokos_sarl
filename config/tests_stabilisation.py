"""Tests d'intégration de maintenance, erreurs et vérification Turnstile."""
import json
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from config.turnstile import verify_turnstile


class ErrorPagesTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_html_404(self):
        response = self.client.get("/inconnue/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page introuvable", status_code=404)

    @override_settings(DEBUG=False)
    def test_api_404(self):
        response = self.client.get("/api/route-inconnue/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 404)


class MaintenanceTests(TestCase):
    @override_settings(EKAKO_MAINTENANCE=True)
    def test_storefront_and_checkout_503(self):
        self.assertEqual(self.client.get("/").status_code, 503)
        response = self.client.post("/api/checkout/", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "maintenance")

    @override_settings(EKAKO_MAINTENANCE=True)
    def test_admin_login_is_not_503(self):
        self.assertNotEqual(self.client.get("/admin/login/").status_code, 503)

    @override_settings(EKAKO_MAINTENANCE=True)
    def test_customer_still_blocked(self):
        user = get_user_model().objects.create_user(
            username="ekako_customer_check", password="abcTest987!"
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get("/boutique/").status_code, 503)


@override_settings(
    EKAKO_TURNSTILE_ENABLED=True,
    EKAKO_TURNSTILE_SITE_KEY="real-site",
    EKAKO_TURNSTILE_SECRET_KEY="real-secret",
    EKAKO_TURNSTILE_HOSTNAME="ekako.example",
)
class CaptchaVerificationTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post("/")
        self.data = {"turnstile_token": "token-example"}

    def verify_mocked(self, response, action="register"):
        with patch(
            "config.turnstile.http_request.urlopen",
            return_value=BytesIO(json.dumps(response).encode("utf-8")),
        ):
            return verify_turnstile(self.request, self.data, action)

    def test_missing_token_fails_closed(self):
        response = verify_turnstile(self.request, {}, "register")
        self.assertEqual(response.status_code, 400)

    def test_valid_token(self):
        self.assertIsNone(
            self.verify_mocked({
                "success": True,
                "hostname": "ekako.example",
                "action": "register",
            })
        )

    def test_wrong_action_rejected(self):
        response = self.verify_mocked({
            "success": True,
            "hostname": "ekako.example",
            "action": "checkout",
        })
        self.assertEqual(response.status_code, 400)

    def test_wrong_hostname_rejected(self):
        response = self.verify_mocked({
            "success": True,
            "hostname": "wrong.example",
            "action": "register",
        })
        self.assertEqual(response.status_code, 400)

    def test_bad_token_rejected(self):
        response = self.verify_mocked({"success": False})
        self.assertEqual(response.status_code, 400)

    def test_unavailable_turnstile_blocks_submission(self):
        with patch("config.turnstile.http_request.urlopen", side_effect=OSError("offline")):
            response = verify_turnstile(self.request, self.data, "register")
        self.assertEqual(response.status_code, 503)

    def test_malformed_cloudflare_response(self):
        response = self.verify_mocked(["not", "a", "dict"])
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=False)
    def test_missing_action_rejected_with_debug_false(self):
        response = self.verify_mocked({
            "success": True,
            "hostname": "ekako.example",
        })
        self.assertEqual(response.status_code, 400)


class CaptchaLocalTestKeys(SimpleTestCase):
    @override_settings(
        DEBUG=True,
        EKAKO_TURNSTILE_ENABLED=True,
        EKAKO_TURNSTILE_SITE_KEY="1x00000000000000000000AA",
        EKAKO_TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA",
        EKAKO_TURNSTILE_HOSTNAME="",
    )
    def test_official_test_keys_without_action(self):
        # Cloudflare's test response contains no action.
        with patch(
            "config.turnstile.http_request.urlopen",
            return_value=BytesIO(b'{"success":true,"hostname":"example.com"}'),
        ):
            response = verify_turnstile(
                RequestFactory().post("/"),
                {"turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"},
                "register",
            )
        self.assertIsNone(response)

    @override_settings(
        DEBUG=False,
        EKAKO_TURNSTILE_ENABLED=True,
        EKAKO_TURNSTILE_SITE_KEY="1x00000000000000000000AA",
        EKAKO_TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA",
        EKAKO_TURNSTILE_HOSTNAME="",
    )
    def test_test_key_exception_forbidden_in_production(self):
        with patch(
            "config.turnstile.http_request.urlopen",
            return_value=BytesIO(b'{"success":true,"hostname":"example.com"}'),
        ):
            response = verify_turnstile(
                RequestFactory().post("/"),
                {"turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"},
                "register",
            )
        self.assertEqual(response.status_code, 400)


class CaptchaDisabledTests(SimpleTestCase):
    @override_settings(EKAKO_TURNSTILE_ENABLED=False)
    def test_disabled_locally(self):
        self.assertIsNone(
            verify_turnstile(RequestFactory().post("/"), {}, "register")
        )
