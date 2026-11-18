from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from config.error_views import server_error


@override_settings(
    EKAKO_MAINTENANCE=True,
    EKAKO_CHECKOUT_MODE="closed",
)
class MaintenanceP5Tests(TestCase):

    def test_public_pages_blocked(self):
        for url in ["/", "/boutique/"]:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 503)
                self.assertEqual(r["Cache-Control"], "no-store")
                self.assertEqual(r["Retry-After"], "600")

    def test_public_api_blocked(self):
        r = self.client.get("/api/products/")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["code"], "maintenance")

    def test_login_remains_accessible(self):
        self.assertEqual(
            self.client.get("/admin/login/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/admin/login/").status_code, 405
        )

    def test_authorized_admin_access(self):
        user = get_user_model().objects.create_superuser(
            username="maintenance_p5_admin",
            email="maintenance-p5@example.com",
            password="Temporary-Test-Password-2026",
        )
        self.client.force_login(user)

        self.assertEqual(
            self.client.get("/boutique/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/admin/orders/").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/products/").status_code, 503
        )

    def test_error_500_template(self):
        request = RequestFactory().get("/erreur-test/")
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"eKAKO", response.content)
