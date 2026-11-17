"""Tests de l'audit Cloudinary en base de données temporaire."""
from io import StringIO
from unittest.mock import patch

from cloudinary.exceptions import NotFound
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.models import Product, ProductGalleryImage


@override_settings(
    EKAKO_MEDIA_STORAGE="cloudinary",
    CLOUDINARY_CLOUD_NAME="test-ekako",
    CLOUDINARY_API_KEY="test-key",
    CLOUDINARY_API_SECRET="test-secret",
)
class AuditCloudinaryImagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.good = Product.objects.create(
            sku="AUDIT-OK", name="Produit valide",
            image="products/available.jpg",
        )
        cls.missing = Product.objects.create(
            sku="AUDIT-MISSING", name="Produit manquant",
            image="products/legacy.jpg",
        )
        cls.bad = Product.objects.create(
            sku="AUDIT-BAD", name="Référence non conforme",
            image="elsewhere/outside.jpg",
        )
        ProductGalleryImage.objects.create(
            product=cls.good, image="products/gallery/supplement.webp",
        )

    @patch("config.cloudinary_storage.cloudinary.config")
    @patch("cloudinary.api.resource")
    def test_reports_available_missing_and_invalid_without_mutation(self, resource, _):
        def answer(public_id, **kwargs):
            if public_id == "products/legacy":
                raise NotFound("not found")
            return {"public_id": public_id}
        resource.side_effect = answer
        stdout = StringIO()
        call_command("audit_cloudinary_images", stdout=stdout)
        report = stdout.getvalue()
        self.assertIn("OK | SKU=AUDIT-OK | principale", report)
        self.assertIn("ABSENTE | SKU=AUDIT-MISSING | principale", report)
        self.assertIn("REFERENCE_INVALIDE | SKU=AUDIT-BAD", report)
        self.assertIn("OK=2", report)
        self.assertIn("ABSENTE=1", report)
        self.assertIn("REFERENCE_INVALIDE=1", report)
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(ProductGalleryImage.objects.count(), 1)
        self.good.refresh_from_db()
        self.assertEqual(self.good.image.name, "products/available.jpg")

    @patch("config.cloudinary_storage.cloudinary.config")
    @patch("cloudinary.api.resource")
    def test_api_failure_is_not_confused_with_missing_asset(self, resource, _):
        resource.side_effect = RuntimeError("private API message")
        stdout, stderr = StringIO(), StringIO()
        call_command("audit_cloudinary_images", stdout=stdout, stderr=stderr)
        report = stdout.getvalue()
        self.assertIn("ERREUR_API", report)
        self.assertNotIn("private API message", report)
        self.assertIn("ne pas les interpréter", stderr.getvalue())

    @override_settings(EKAKO_MEDIA_STORAGE="local")
    def test_requires_cloudinary_configuration(self):
        with self.assertRaises(CommandError):
            call_command("audit_cloudinary_images")

    @patch("config.cloudinary_storage.cloudinary.config")
    @patch("cloudinary.api.resource")
    def test_limit_bounds_remote_checks(self, resource, _):
        # La limite compte les références inspectées, y compris celles
        # invalides et rejetées AVANT tout appel réseau.
        # Tri des SKU : AUDIT-BAD, AUDIT-MISSING, AUDIT-OK.
        resource.return_value = {}
        stdout = StringIO()
        call_command("audit_cloudinary_images", limit=1, stdout=stdout)
        self.assertIn("références=1", stdout.getvalue())
        self.assertIn("REFERENCE_INVALIDE | SKU=AUDIT-BAD", stdout.getvalue())
        self.assertEqual(resource.call_count, 0)

        stdout = StringIO()
        resource.reset_mock()
        call_command("audit_cloudinary_images", limit=2, stdout=stdout)
        self.assertIn("références=2", stdout.getvalue())
        resource.assert_called_once_with("products/legacy", resource_type="image")
