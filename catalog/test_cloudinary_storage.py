"""Tests unitaires du stockage d'images eKAKO, sans appel Cloudinary réel."""

from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from config.cloudinary_storage import CloudinaryMediaStorage


@override_settings(
    CLOUDINARY_CLOUD_NAME="ekako-test",
    CLOUDINARY_API_KEY="key-test",
    CLOUDINARY_API_SECRET="secret-test",
)
class CloudinaryMediaStorageTests(SimpleTestCase):
    @patch("config.cloudinary_storage.cloudinary.config")
    def setUp(self, config_mock):
        self.storage = CloudinaryMediaStorage()

    @patch("config.cloudinary_storage.cloudinary.uploader.upload")
    def test_product_upload_stores_cloudinary_name(self, upload_mock):
        upload_mock.return_value = {
            "public_id": "products/abc123",
            "format": "jpg",
        }
        name = self.storage.save("products/chaussure.jpg", ContentFile(b"example"))
        self.assertEqual(name, "products/abc123.jpg")
        self.assertEqual(upload_mock.call_args.kwargs["resource_type"], "image")
        self.assertFalse(upload_mock.call_args.kwargs["overwrite"])

    @patch("config.cloudinary_storage.cloudinary.CloudinaryImage")
    def test_https_url_uses_cloudinary(self, image_mock):
        image_mock.return_value.build_url.return_value = (
            "https://res.cloudinary.com/ekako-test/image/upload/products/abc123.jpg"
        )
        url = self.storage.url("products/abc123.jpg")
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(image_mock.call_args.args[0], "products/abc123")
        self.assertTrue(image_mock.return_value.build_url.call_args.kwargs["secure"])

    @patch("config.cloudinary_storage.cloudinary.uploader.destroy")
    def test_gallery_delete_only_targets_image(self, destroy_mock):
        self.storage.delete("products/gallery/abc123.webp")
        destroy_mock.assert_called_once_with(
            "products/gallery/abc123", resource_type="image", invalidate=True
        )

    def test_rejects_wrong_media_path(self):
        with self.assertRaises(SuspiciousFileOperation):
            self.storage.url("admin/secret.jpg")

    def test_rejects_invalid_format(self):
        with self.assertRaises(SuspiciousFileOperation):
            self.storage.url("products/abc123.svg")


class CloudinaryMediaStorageConfigTests(SimpleTestCase):
    @override_settings(
        CLOUDINARY_CLOUD_NAME="",
        CLOUDINARY_API_KEY="",
        CLOUDINARY_API_SECRET="",
    )
    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            CloudinaryMediaStorage()
