"""Régression Paiements V1A : exécution avec DB temporaire seulement."""
import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from orders.models import Order, PaymentStatusLog


class PaymentControlsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username='ekako_test_payment_admin', email='test-payments@example.com',
            password='long-test-password-2026'
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def make_order(self, number='TEST-PAY-MOMO', method='MTN Mobile Money', status='received'):
        return Order.objects.create(
            order_no=number, customer_name='Client de test', customer_phone='699000111',
            city='Yaounde', quarter='Bastos', address='Adresse test',
            pay_method=method, status=status, subtotal=10000, total=10000,
        )

    def payment(self, order, status, ref='', verified=False, **more):
        data = {'payment_status':status, 'payment_ref':ref, 'verified':verified, **more}
        return self.client.post(
            reverse('admin_update_payment_status_api', kwargs={'order_no':order.order_no}),
            data=json.dumps(data), content_type='application/json'
        )

    def order_status(self, order, status):
        return self.client.post(
            reverse('admin_update_status_api', kwargs={'order_no':order.order_no}),
            data=json.dumps({'status':status}), content_type='application/json'
        )

    def test_momo_cannot_prepare_without_payment(self):
        order = self.make_order()
        response = self.order_status(order, 'preparing')
        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, 'received')

    def test_momo_can_prepare_after_manual_confirmation(self):
        order = self.make_order()
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-1', True).status_code, 200)
        self.assertEqual(self.order_status(order, 'preparing').status_code, 200)
        self.assertEqual(self.order_status(order, 'shipped').status_code, 200)

    def test_manual_paid_requires_verified_and_reference(self):
        order = self.make_order()
        self.assertEqual(self.payment(order, 'paid').status_code, 400)
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-2', False).status_code, 400)
        self.assertEqual(self.payment(order, 'paid', '', True).status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, 'unpaid')
        self.assertEqual(PaymentStatusLog.objects.count(), 0)

    def test_success_is_logged_once_and_idempotent(self):
        order = self.make_order()
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-3', True).status_code, 200)
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-3', True).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, 'paid')
        self.assertEqual(order.payment_reference, 'MOMO-PAY-3')
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(PaymentStatusLog.objects.filter(order=order).count(), 1)
        self.assertEqual(PaymentStatusLog.objects.get(order=order).changed_by, self.admin)

    def test_duplicate_payment_reference_refused(self):
        a = self.make_order('TEST-PAY-REF-A')
        b = self.make_order('TEST-PAY-REF-B')
        self.assertEqual(self.payment(a, 'paid', 'MOMO-PAY-4', True).status_code, 200)
        self.assertEqual(self.payment(b, 'paid', 'MOMO-PAY-4', True).status_code, 409)
        b.refresh_from_db()
        self.assertEqual(b.payment_state, 'unpaid')

    def test_paid_cannot_be_downgraded(self):
        order = self.make_order()
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-5', True).status_code, 200)
        self.assertEqual(self.payment(order, 'pending').status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, 'paid')

    def test_cod_can_prepare_ship_before_payment(self):
        order = self.make_order('TEST-PAY-COD', 'Paiement a la livraison (optionnel)')
        self.assertEqual(self.order_status(order, 'preparing').status_code, 200)
        self.assertEqual(self.order_status(order, 'shipped').status_code, 200)
        self.assertEqual(self.payment(order, 'paid', 'CASH-REC-1', True).status_code, 409)
        self.assertEqual(self.order_status(order, 'delivered').status_code, 200)
        self.assertEqual(self.payment(order, 'paid', 'CASH-REC-1', True).status_code, 200)

    def test_cancelled_order_paid_manually_blocked(self):
        order = self.make_order('TEST-PAY-CANCELLED', status='cancelled')
        self.assertEqual(self.payment(order, 'paid', 'MOMO-PAY-6', True).status_code, 409)

    def test_malformed_json_no_change(self):
        order = self.make_order()
        url = reverse('admin_update_payment_status_api', kwargs={'order_no':order.order_no})
        response = self.client.post(url, data='{bad', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.payment_state, 'unpaid')

    def test_pending_change_is_audited(self):
        order = self.make_order()
        self.assertEqual(self.payment(order, 'pending').status_code, 200)
        self.assertEqual(PaymentStatusLog.objects.get(order=order).new_state, 'pending')

    def test_checkout_rejects_unknown_payment_method(self):
        payload = {
            'customer': {'name':'Test', 'phone':'699111222', 'city':'Yaounde',
                         'quarter':'Bastos', 'address':'Adresse test'},
            'items': [{'sku':'INVALID', 'size':'M', 'qty':1}],
            'pay_method': 'Paiement fictif livraison',
        }
        response = self.client.post(reverse('checkout_api'), data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Moyen de paiement', response.json()['error'])
