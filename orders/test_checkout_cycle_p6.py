import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Size, Variant
from orders.models import Order, CheckoutAttempt
from orders.whatsapp_reservations import expire_whatsapp_reservations
from sourcing.models import ProcurementLine, DeliveryTask


@override_settings(
    EKAKO_CHECKOUT_MODE="whatsapp",
    EKAKO_WHATSAPP_NUMBER="237699001122",
    EKAKO_TURNSTILE_ENABLED=False,
    IS_PRODUCTION=False,
)
class CheckoutCycleP6Tests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            sku="EK-P6-TEST-001",
            name="Produit fictif P6",
            category="Textile",
            retail_price=15000,
            reseller_price=12000,
            reseller_moq=1,
            variant_type="clothing_size",
            is_active=True,
        )
        cls.size = Size.objects.create(label="P6-M")
        cls.variant = Variant.objects.create(
            product=cls.product,
            size=cls.size,
            stock_qty=10,
        )

    def checkout(self, key):
        payload = {
            "customer": {
                "name": "Client fictif P6",
                "phone": "699001122",
                "city": "Yaounde",
                "quarter": "Bastos",
                "address": "Adresse fictive P6",
            },
            "items": [{
                "sku": self.product.sku,
                "size": self.size.label,
                "qty": 2,
            }],
        }

        return self.client.post(
            reverse("checkout_api"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_reservation_whatsapp(self):
        response = self.checkout("ekako-p6-reservation-0001")
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(
            order_no=response.json()["orderNo"]
        )

        self.assertEqual(order.checkout_channel, "whatsapp")
        self.assertEqual(order.status, "received")
        self.assertEqual(order.payment_state, "unpaid")
        self.assertIsNotNone(order.reservation_expires_at)
        self.assertEqual(order.items.count(), 1)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 8)

        self.assertEqual(
            ProcurementLine.objects.filter(
                order_item__order=order
            ).count(), 1
        )
        self.assertTrue(
            DeliveryTask.objects.filter(order=order).exists()
        )

        print("P6 : réservation et stock OK")

    def test_idempotence(self):
        key = "ekako-p6-idempotence-0002"
        first = self.checkout(key)
        second = self.checkout(key)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.json()["orderNo"],
            second.json()["orderNo"],
        )
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 8)

        print("P6 : aucune double commande OK")

    def test_expiration_and_restock_once(self):
        response = self.checkout("ekako-p6-expiration-0003")
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(
            order_no=response.json()["orderNo"]
        )

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_qty, 8)

        Order.objects.filter(pk=order.pk).update(
            reservation_expires_at=(
                timezone.now() - timedelta(minutes=1)
            )
        )

        self.assertEqual(expire_whatsapp_reservations(), 1)
        self.assertEqual(expire_whatsapp_reservations(), 0)

        order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(order.payment_state, "unpaid")
        self.assertEqual(self.variant.stock_qty, 10)
        self.assertEqual(order.status_logs.count(), 1)

        print("P6 : expiration et restitution du stock OK")


    def admin_post(self, name, order_no, payload):
        return self.client.post(
            reverse(name, kwargs={"order_no": order_no}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def make_order_as_admin(self, key):
        response = self.checkout(key)
        self.assertEqual(response.status_code, 200)
        order_no = response.json()["orderNo"]

        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_superuser(
            username="ekako_admin_" + key[-4:],
            email="admin-p6@example.com",
            password="Temporary-Test-Password-2026",
        )
        self.client.force_login(admin)
        return order_no

    def test_preparation_avant_paiement_bloquee(self):
        order_no = self.make_order_as_admin(
            "ekako-p6-payment-block-0004"
        )
        response = self.admin_post(
            "admin_update_status_api",
            order_no,
            {"status": "preparing"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            Order.objects.get(order_no=order_no).status,
            "received",
        )

    def test_paiement_non_verifie_refuse(self):
        order_no = self.make_order_as_admin(
            "ekako-p6-payment-check-0005"
        )

        method = self.admin_post(
            "admin_confirm_whatsapp_payment_method_api",
            order_no,
            {
                "pay_method": "MTN Mobile Money",
                "confirmed_with_customer": True,
            },
        )
        self.assertEqual(method.status_code, 200)

        payment = self.admin_post(
            "admin_update_payment_status_api",
            order_no,
            {
                "payment_status": "paid",
                "payment_ref": "REF-P6-0005",
                "verified": False,
            },
        )
        self.assertEqual(payment.status_code, 400)
        self.assertEqual(
            Order.objects.get(order_no=order_no).payment_state,
            "unpaid",
        )

    def test_confirmation_manuelle_auditee(self):
        order_no = self.make_order_as_admin(
            "ekako-p6-payment-audit-0006"
        )

        method = self.admin_post(
            "admin_confirm_whatsapp_payment_method_api",
            order_no,
            {
                "pay_method": "MTN Mobile Money",
                "confirmed_with_customer": True,
            },
        )
        self.assertEqual(method.status_code, 200)

        payment = self.admin_post(
            "admin_update_payment_status_api",
            order_no,
            {
                "payment_status": "paid",
                "payment_ref": "REF-P6-0006",
                "verified": True,
            },
        )
        self.assertEqual(payment.status_code, 200)

        order = Order.objects.get(order_no=order_no)
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(
            order.payment_reference, "REF-P6-0006"
        )
        self.assertIsNotNone(order.paid_at)
        self.assertTrue(order.payment_logs.filter(
            new_state="paid"
        ).exists())


    def make_paid_order(self, key):
        order_no = self.make_order_as_admin(key)

        method = self.admin_post(
            "admin_confirm_whatsapp_payment_method_api",
            order_no,
            {
                "pay_method": "MTN Mobile Money",
                "confirmed_with_customer": True,
            },
        )
        self.assertEqual(method.status_code, 200)

        payment = self.admin_post(
            "admin_update_payment_status_api",
            order_no,
            {
                "payment_status": "paid",
                "payment_ref": "REF-" + key,
                "verified": True,
            },
        )
        self.assertEqual(payment.status_code, 200)
        return order_no

    def change_status(self, order_no, status):
        return self.admin_post(
            "admin_update_status_api",
            order_no,
            {"status": status},
        )

    def test_preparation_sans_fournisseur_bloquee(self):
        order_no = self.make_paid_order(
            "ekako-p6-supplier-block-0007"
        )

        response = self.change_status(
            order_no, "preparing"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            Order.objects.get(order_no=order_no).status,
            "received",
        )

    def test_expedition_sans_collecte_bloquee(self):
        from sourcing.models import ProcurementLine

        order_no = self.make_paid_order(
            "ekako-p6-collect-block-0008"
        )

        lines = ProcurementLine.objects.filter(
            order_item__order__order_no=order_no
        )
        self.assertEqual(lines.count(), 1)
        lines.update(status="confirmed", unit_cost=9000)

        self.assertEqual(
            self.change_status(
                order_no, "preparing"
            ).status_code, 200
        )
        self.assertEqual(
            self.change_status(
                order_no, "shipped"
            ).status_code, 409
        )

    def test_livreur_et_remise_obligatoires(self):
        from sourcing.models import ProcurementLine, DeliveryTask

        order_no = self.make_paid_order(
            "ekako-p6-delivery-block-0009"
        )

        ProcurementLine.objects.filter(
            order_item__order__order_no=order_no
        ).update(status="collected", unit_cost=9000)

        self.assertEqual(
            self.change_status(
                order_no, "preparing"
            ).status_code, 200
        )

        self.assertEqual(
            self.change_status(
                order_no, "shipped"
            ).status_code, 409
        )

        delivery = DeliveryTask.objects.get(
            order__order_no=order_no
        )
        delivery.courier_name = "Livreur fictif P6"
        delivery.status = "assigned"
        delivery.save()

        self.assertEqual(
            self.change_status(
                order_no, "shipped"
            ).status_code, 200
        )

        self.assertEqual(
            self.change_status(
                order_no, "delivered"
            ).status_code, 409
        )

        delivery.status = "delivered"
        delivery.save()

        self.assertEqual(
            self.change_status(
                order_no, "delivered"
            ).status_code, 200
        )
        self.assertEqual(
            Order.objects.get(order_no=order_no).status,
            "delivered",
        )
