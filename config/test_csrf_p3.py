from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class EkakoCSRFTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="p3_csrf_admin",
            email="p3-csrf@example.com",
            password="P3-Test-Password-2026",
        )

    def test_sensitive_admin_actions_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)

        endpoints = [
            "/api/admin/inventory/adjust/",
            "/api/admin/products/save/",
            "/api/admin/order/FAKE-P3/status/",
            "/api/admin/order/FAKE-P3/payment-status/",
            "/api/admin/order/FAKE-P3/cod-collection/",
            "/api/admin/order/FAKE-P3/courier-payout/",
            "/api/admin/reseller/applications/999999/approve/",
        ]

        for url in endpoints:
            with self.subTest(url=url):
                response = client.post(
                    url,
                    data="{}",
                    content_type="application/json",
                )

                print(
                    "CSRF P3.4:",
                    response.status_code,
                    url,
                )

                self.assertEqual(
                    response.status_code,
                    403,
                    f"Protection CSRF absente : {url}",
                )
