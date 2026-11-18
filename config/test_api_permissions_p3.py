from django.contrib.auth import get_user_model
from django.test import TestCase


class ApiPermissionsDiagnosticTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(
            username="p3_permissions_customer",
            password="P3-Test-Password-2026",
        )

    def test_admin_api_permissions_matrix(self):
        endpoints = [
            "/api/admin/orders/",
            "/api/admin/inventory/",
            "/api/admin/products/",
            "/api/admin/reseller/applications/",
        ]

        print("\\nDIAGNOSTIC P3.2 — Permissions API")

        for role in ("anonymous", "customer"):
            self.client.logout()

            if role == "customer":
                self.client.force_login(self.customer)

            for url in endpoints:
                response = self.client.get(url)
                print(
                    f"{role:10} | "
                    f"{response.status_code} | {url}"
                )

                # Aucun utilisateur non autorisé
                # ne doit recevoir les données.
                expected = (
                    401 if role == "anonymous" else 403
                )
                self.assertEqual(
                    response.status_code, expected
                )

        print("DIAGNOSTIC P3.2 TERMINE")
