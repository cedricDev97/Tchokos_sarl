"""Tests de sécurisation P1 du Django Admin et des rôles sensibles."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.sites import site
from django.test import Client, TestCase, override_settings

from accounts.models import LoginAttemptCounter


@override_settings(EKAKO_MAINTENANCE=False)
class AdminLoginThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="secure_admin_test",
            password="StrongAdminTest123!",
            email="admin@example.invalid",
        )

    def submit(self, username="secure_admin_test", password="incorrect", ip="192.0.2.90"):
        return self.client.post(
            "/admin/login/",
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def test_five_failures_block_correct_password(self):
        for _ in range(5):
            self.assertEqual(self.submit().status_code, 200)
        response = self.submit(password="StrongAdminTest123!")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_successful_login_still_works(self):
        response = self.submit(password="StrongAdminTest123!")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.get("/admin/").status_code == 200)

    def test_invalid_then_success_resets_username_pair(self):
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.submit(password="StrongAdminTest123!").status_code, 302)
        self.client.logout()
        self.assertEqual(self.submit().status_code, 200)

    def test_username_spraying_blocked_per_ip(self):
        for i in range(20):
            self.assertEqual(
                self.submit(username=f"missing_{i}").status_code, 200,
            )
        self.assertEqual(self.submit(password="StrongAdminTest123!").status_code, 429)

    def test_get_login_is_unchanged(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_csrf_failure_does_not_increment_counter(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/admin/login/",
            {"username": "secure_admin_test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(LoginAttemptCounter.objects.count(), 0)


@override_settings(EKAKO_MAINTENANCE=False)
class SensitiveIdentityAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        model = get_user_model()
        cls.superuser = model.objects.create_superuser(
            username="secure_superuser", email="super@example.invalid",
            password="StrongPassword123!",
        )
        cls.staff = model.objects.create_user(
            username="permitted_staff", password="StrongPassword123!",
            is_staff=True,
        )
        auth_permissions = Permission.objects.filter(
            content_type__app_label="auth",
            codename__in={
                "view_user", "change_user", "add_user", "delete_user",
                "view_group", "change_group", "add_group", "delete_group",
            },
        )
        cls.staff.user_permissions.add(*auth_permissions)
        cls.group = Group.objects.create(name="admin_orders")

    def test_staff_with_auth_permissions_cannot_manage_users_or_groups(self):
        self.client.force_login(self.staff)
        for url in (
            "/admin/auth/user/",
            "/admin/auth/user/add/",
            f"/admin/auth/user/{self.staff.pk}/change/",
            "/admin/auth/group/",
            "/admin/auth/group/add/",
            f"/admin/auth/group/{self.group.pk}/change/",
        ):
            self.assertIn(self.client.get(url).status_code, (302, 403), msg=url)

    def test_superuser_retains_identity_admin(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get("/admin/auth/user/").status_code, 200)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 200)

    def test_admin_model_permissions_are_superuser_only(self):
        from django.contrib.auth.models import Group
        for model in (get_user_model(), Group):
            model_admin = site._registry[model]
            self.assertFalse(model_admin.has_change_permission(
                type("Request", (), {"user": self.staff})()
            ))
            self.assertTrue(model_admin.has_change_permission(
                type("Request", (), {"user": self.superuser})()
            ))
