from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone


class AdminSessionSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            username="p3_admin",
            email="p3@example.com",
            password="P3-Test-Password-2026",
        )
        cls.customer = User.objects.create_user(
            username="p3_customer",
            password="P3-Test-Password-2026",
        )

    def set_admin_timestamp(self, key, elapsed):
        session = self.client.session
        session[key] = (
            timezone.now() - elapsed
        ).isoformat()
        session.save()

    def test_admin_session_active(self):
        self.client.force_login(self.admin)
        response = self.client.get("/api/admin/me/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])

    def test_admin_idle_expiration(self):
        self.client.force_login(self.admin)
        self.client.get("/api/admin/me/")
        self.set_admin_timestamp(
            "_ekako_admin_last_active",
            timedelta(minutes=31),
        )
        response = self.client.get("/api/admin/me/")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(
            self.client.session.get("_auth_user_id")
        )

    def test_admin_absolute_expiration(self):
        self.client.force_login(self.admin)
        self.client.get("/api/admin/me/")
        self.set_admin_timestamp(
            "_ekako_admin_created",
            timedelta(hours=9),
        )
        response = self.client.get("/api/admin/me/")
        self.assertEqual(response.status_code, 401)

    def test_customer_session_preserved(self):
        self.client.force_login(self.customer)
        response = self.client.get("/api/admin/me/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertFalse(
            self.client.session.get(
                "_ekako_admin_created"
            )
        )

    def test_admin_cookie_browser_close(self):
        self.client.force_login(self.admin)
        self.client.get("/api/admin/me/")
        self.assertEqual(
            self.client.session.get_expire_at_browser_close(),
            True,
        )
