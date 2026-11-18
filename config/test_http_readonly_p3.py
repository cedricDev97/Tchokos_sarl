from django.contrib.auth import get_user_model
from django.test import TestCase


class ReadOnlyAdminAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="p3_readonly_admin",
            email="p3-readonly@example.com",
            password="P3-Test-Password-2026",
        )

    def test_readonly_endpoints(self):
        self.client.force_login(self.admin)

        urls = [
            "/api/admin/stats/",
            "/api/admin/analytics/",
            "/api/admin/orders/P3-FAKE/timeline/",
            "/api/admin/order/P3-FAKE/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.post(
                    url,
                    data="{}",
                    content_type="application/json",
                )

                print(
                    "HTTP P3.6:",
                    response.status_code,
                    url,
                )

                self.assertEqual(
                    response.status_code, 405
                )
