import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone


class AdminSessionLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "P3-Test-Password-2026"
        cls.admin = get_user_model().objects.create_superuser(
            username="p3_lifecycle_admin",
            email="p3-lifecycle@example.com",
            password=cls.password,
        )

        cls.manager = get_user_model().objects.create_user(
            username="p3_lifecycle_manager",
            password=cls.password,
        )
        cls.group = Group.objects.create(
            name="admin_inventory"
        )
        cls.manager.groups.add(cls.group)

    def test_relogin_after_expiration(self):
        self.client.force_login(self.admin)
        self.client.get("/api/admin/me/")

        session = self.client.session
        session["_ekako_admin_last_active"] = (
            timezone.now() - timedelta(minutes=31)
        ).isoformat()
        session.save()

        response = self.client.post(
            "/api/admin/login/",
            data=json.dumps({
                "username": self.admin.username,
                "password": self.password,
            }),
            content_type="application/json",
        )

        print(
            "Reconnexion après expiration :",
            response.status_code,
        )
        self.assertEqual(response.status_code, 200)

        check = self.client.get("/api/admin/me/")
        self.assertEqual(check.status_code, 200)
        self.assertTrue(check.json()["authenticated"])

    def test_permissions_revoked(self):
        self.client.force_login(self.manager)

        url = "/api/admin/inventory/"
        initial = self.client.get(url)
        self.assertEqual(initial.status_code, 200)

        self.manager.groups.remove(self.group)

        response = self.client.get(url)
        print(
            "Accès après retrait des droits :",
            response.status_code,
        )
        self.assertEqual(response.status_code, 403)
