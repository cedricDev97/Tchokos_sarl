"""Sécurité de l'accès HTTP à l'audit Cloudinary pour Render Free."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from catalog.models import Product


@override_settings(
    EKAKO_MAINTENANCE=False,
    EKAKO_MEDIA_STORAGE="cloudinary",
    CLOUDINARY_CLOUD_NAME="test-cloud",
    CLOUDINARY_API_KEY="test-key",
    CLOUDINARY_API_SECRET="test-secret",
)
class CloudinaryAuditHTTPTests(TestCase):
    url = "/api/admin/cloudinary-audit/"

    def setUp(self):
        self.client = Client()
        model = get_user_model()
        self.admin = model.objects.create_superuser(
            username="audit-admin", email="audit@example.invalid",
            password="AuditTestPass123!",
        )
        self.staff = model.objects.create_user(
            username="audit-staff", password="AuditTestPass123!",
            is_staff=True,
        )
        Product.objects.create(sku="AUDIT-HTTP", name="Test audit", image="products/present.jpg")

    @patch("cloudinary.api.resource", return_value={"public_id": "products/present"})
    def test_superuser_sees_read_only_report(self, resource):
        self.client.force_login(self.admin)
        with patch("config.cloudinary_storage.cloudinary.config"):
            response = self.client.get(self.url, {"limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["read_only"])
        self.assertIn("SKU=AUDIT-HTTP", response.json()["report"])
        self.assertEqual(response["Cache-Control"], "no-store, private")
        resource.assert_called_once_with("products/present", resource_type="image")
        self.assertEqual(Product.objects.count(), 1)

    @patch("cloudinary.api.resource")
    def test_non_superuser_is_denied(self, resource):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        resource.assert_not_called()

    @patch("cloudinary.api.resource")
    def test_anonymous_is_denied(self, resource):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        resource.assert_not_called()

    @patch("cloudinary.api.resource")
    def test_invalid_limit_cannot_trigger_api_call(self, resource):
        self.client.force_login(self.admin)
        for limit in ("0", "101", "invalid"):
            self.assertEqual(self.client.get(self.url, {"limit": limit}).status_code, 400)
        resource.assert_not_called()

    @override_settings(EKAKO_MEDIA_STORAGE="local")
    @patch("cloudinary.api.resource")
    def test_local_storage_is_denied(self, resource):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 503)
        resource.assert_not_called()
