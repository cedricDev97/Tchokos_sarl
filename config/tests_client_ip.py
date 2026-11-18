"""Contrôles du fournisseur IP anti-bruteforce (sans accès réseau)."""
from django.test import SimpleTestCase, override_settings, RequestFactory
from accounts.login_throttle import _keys as login_keys
from orders.track_throttle import _keys as track_keys
from config.client_ip import client_ip_for_throttle


class ClientIPTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def req(self, remote, cf=None, xff=None):
        args = {"REMOTE_ADDR": remote}
        if cf is not None:
            args["HTTP_CF_CONNECTING_IP"] = cf
        if xff is not None:
            args["HTTP_X_FORWARDED_FOR"] = xff
        return self.factory.get("/", **args)

    @override_settings(EKAKO_CLIENT_IP_SOURCE="remote")
    def test_default_ignores_spoofed_headers(self):
        r = self.req("198.51.100.1", "203.0.113.15", "192.0.2.42")
        self.assertEqual(client_ip_for_throttle(r), "198.51.100.1")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_cf_header_used_in_opt_in_only(self):
        r = self.req("10.0.0.1", "203.0.113.15", "192.0.2.42")
        self.assertEqual(client_ip_for_throttle(r), "203.0.113.15")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_strictly_rejects_multiple_ip_header(self):
        r = self.req("10.0.0.1", "203.0.113.15, 198.51.100.9")
        self.assertEqual(client_ip_for_throttle(r), "10.0.0.1")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_strictly_rejects_fake_ip(self):
        r = self.req("10.0.0.1", "invalid-address", "203.0.113.15")
        self.assertEqual(client_ip_for_throttle(r), "10.0.0.1")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_supports_ipv6(self):
        r = self.req("10.0.0.1", "2001:db8::123")
        self.assertEqual(client_ip_for_throttle(r), "2001:db8::123")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_never_falls_back_to_xff(self):
        r = self.req("10.0.0.1", xff="203.0.113.99")
        self.assertEqual(client_ip_for_throttle(r), "10.0.0.1")

    @override_settings(EKAKO_CLIENT_IP_SOURCE="cloudflare")
    def test_distinct_clients_have_distinct_login_and_tracking_keys(self):
        a = self.req("10.0.0.1", "203.0.113.1")
        b = self.req("10.0.0.1", "203.0.113.2")
        self.assertNotEqual(login_keys(a, "admin"), login_keys(b, "admin"))
        self.assertNotEqual(track_keys(a, "EKAKO000001"), track_keys(b, "EKAKO000001"))
