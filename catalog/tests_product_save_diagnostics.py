"""Tests des traces de diagnostic, en base de test Django uniquement."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings

from config.middleware import ProductSaveDiagnosticMiddleware


class ProductSaveDiagnosticUnitTests(SimpleTestCase):
    def setUp(self):
        self.middleware = ProductSaveDiagnosticMiddleware(lambda request: None)
        self.factory = RequestFactory()

    def test_only_product_save_logs_an_error(self):
        exception = RuntimeError("hidden-api-secret-value")
        request = self.factory.post("/api/admin/products/save/")
        request._ekako_product_save_stage = "gallery_images_save"
        with self.assertLogs("ekako.product_save", level="ERROR") as logs:
            result = self.middleware.process_exception(request, exception)
        self.assertIsNone(result)
        message = logs.output[0]
        self.assertIn("EKAKO_PRODUCT_SAVE_FAILURE", message)
        self.assertIn("stage=gallery_images_save", message)
        self.assertIn("exception_type=RuntimeError", message)
        self.assertNotIn("hidden-api-secret-value", message)

    def test_other_routes_not_logged(self):
        request = self.factory.post("/api/checkout/")
        with patch("logging.getLogger") as get_logger:
            self.assertIsNone(
                self.middleware.process_exception(request, RuntimeError("other"))
            )
        get_logger.assert_not_called()


@override_settings(EKAKO_MAINTENANCE=False)
class ProductSaveDiagnosticIntegrationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="ekako_product_diagnostic_admin",
            email="catalog-test@example.invalid",
            password="StrongTestPassword123!",
        )
        self.browser = Client(raise_request_exception=False)
        self.browser.force_login(self.admin)

    def test_unexpected_product_save_error_returns_500_and_logs_stage(self):
        payload = {
            "sku": "EKAKO-LOG-TEST",
            "name": "Test diagnostic",
            "retail_price": "1000",
            "reseller_price": "900",
            "reseller_moq": "1",
            "variants_json": json.dumps([{"size": "M", "stock_qty": 2}]),
        }
        from catalog.models import Product
        with patch.object(Product, "save", side_effect=OSError("hidden-token")):
            with self.assertLogs("ekako.product_save", level="ERROR") as logs:
                response = self.browser.post("/api/admin/products/save/", payload)
        self.assertEqual(response.status_code, 500)
        self.assertIn("primary_product_and_image_save", logs.output[0])
        self.assertIn("exception_type=OSError", logs.output[0])
        self.assertNotIn("hidden-token", logs.output[0])
        self.assertEqual(Product.objects.count(), 0)
