"""Tests de limitation de la connexion eKAKO sur la base temporaire Django."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import LoginAttemptCounter


@override_settings(EKAKO_TURNSTILE_ENABLED=False, EKAKO_MAINTENANCE=False)
class LoginThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="client_limit_test",
            password="GoodPass123!Secure",
        )

    def login(self, password, username="client_limit_test", ip="192.0.2.10"):
        return self.client.post(
            "/api/admin/login/",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
            REMOTE_ADDR=ip,
        )

    def test_fifth_failure_blocks_sixth_attempt(self):
        for _ in range(5):
            response = self.login("wrong-pass")
            self.assertEqual(response.status_code, 401)
        response = self.login("GoodPass123!Secure")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(response.json()["ok"], False)

    def test_success_resets_specific_pair(self):
        self.assertEqual(self.login("wrong").status_code, 401)
        self.assertEqual(self.login("GoodPass123!Secure").status_code, 200)
        self.assertEqual(self.login("wrong").status_code, 401)
        # Le compteur pair repart de 1 après une connexion réussie.
        # L'autre compteur, lié à l'IP, peut conserver l'historique.
        self.assertTrue(LoginAttemptCounter.objects.filter(failures=1).exists())

    def test_automatic_expiration(self):
        for _ in range(5):
            self.login("wrong")
        self.assertEqual(self.login("GoodPass123!Secure").status_code, 429)
        LoginAttemptCounter.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.login("GoodPass123!Secure").status_code, 200)

    def test_case_insensitive_username_counter(self):
        for index in range(5):
            user = "client_limit_test" if index % 2 == 0 else "CLIENT_LIMIT_TEST"
            self.assertEqual(self.login("wrong", username=user).status_code, 401)
        self.assertEqual(self.login("GoodPass123!Secure").status_code, 429)

    def test_other_ip_does_not_inherit_pair_block(self):
        for _ in range(5):
            self.login("wrong")
        self.assertEqual(self.login("GoodPass123!Secure", ip="192.0.2.11").status_code, 200)

    def test_per_ip_limit_prevents_username_spraying(self):
        for n in range(20):
            self.assertEqual(
                self.login("wrong", username=f"unknown_{n}").status_code,
                401,
            )
        self.assertEqual(self.login("GoodPass123!Secure").status_code, 429)

    def test_missing_credentials_not_recorded(self):
        response = self.login("", username="")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LoginAttemptCounter.objects.count(), 0)
