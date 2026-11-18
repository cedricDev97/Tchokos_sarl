from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase


class EkakoRoleSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.users = {}

        cls.users["superadmin"] = User.objects.create_superuser(
            username="p3_superadmin",
            email="p3@example.com",
            password="P3-Test-Password-2026",
        )

        roles = {
            "orders": "admin_orders",
            "inventory": "admin_inventory",
            "resellers": "admin_resellers",
        }

        for role, group_name in roles.items():
            user = User.objects.create_user(
                username=f"p3_{role}",
                password="P3-Test-Password-2026",
            )
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
            cls.users[role] = user

    def test_role_matrix(self):
        endpoints = {
            "orders": "/api/admin/orders/",
            "inventory": "/api/admin/inventory/",
            "resellers": "/api/admin/reseller/applications/",
        }

        for role, user in self.users.items():
            self.client.force_login(user)

            for permission, url in endpoints.items():
                response = self.client.get(url)

                expected = (
                    200 if role == "superadmin"
                    or role == permission else 403
                )

                print(
                    f"{role:12} | {permission:10} | "
                    f"{response.status_code}"
                )

                self.assertEqual(
                    response.status_code,
                    expected,
                    f"{role} sur {url}",
                )

    def test_read_only_endpoints_reject_post(self):
        self.client.force_login(self.users["superadmin"])

        endpoints = [
            "/api/admin/orders/",
            "/api/admin/inventory/",
            "/api/admin/products/",
            "/api/admin/reseller/applications/",
        ]

        for url in endpoints:
            response = self.client.post(
                url,
                data="{}",
                content_type="application/json",
            )

            print(
                f"POST {url}: HTTP {response.status_code}"
            )

            self.assertEqual(
                response.status_code,
                405,
                f"POST interdit attendu sur {url}",
            )
