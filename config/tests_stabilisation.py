from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, override_settings
from django.test import RequestFactory
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
        user = get_user_model().objects.create_user(username="ekako_customer_check", password="abcTest987!")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/boutique/").status_code, 503)

class CaptchaTests(SimpleTestCase):
    @override_settings(EKAKO_TURNSTILE_ENABLED=True, EKAKO_TURNSTILE_SITE_KEY="public", EKAKO_TURNSTILE_SECRET_KEY="private")
    def test_empty_captcha(self):
        response = verify_turnstile(RequestFactory().post("/"), {}, "register")
        self.assertEqual(response.status_code, 400)
    @override_settings(EKAKO_TURNSTILE_ENABLED=False)
    def test_local_disabled(self):
        self.assertIsNone(verify_turnstile(RequestFactory().post("/"), {}, "register"))
