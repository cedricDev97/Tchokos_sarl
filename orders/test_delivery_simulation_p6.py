from django.test import SimpleTestCase

from orders.delivery_simulation import simulate_delivery


class DeliverySimulationP6Tests(SimpleTestCase):

    def simulate(self, **overrides):
        values = {
            "product_revenue_fcfa": 20000,
            "supplier_cost_fcfa": 13000,
            "distance_km": 5,
            "weight_grams": 1000,
            "pickup_count": 1,
            "payment_fee_fcfa": 300,
            "other_cost_fcfa": 250,
            "minimum_margin_fcfa": 2000,
        }
        values.update(overrides)
        return simulate_delivery(**values)

    def test_course_simple(self):
        result = self.simulate()
        self.assertEqual(result["delivery_cost_fcfa"], 3000)
        self.assertEqual(
            result["margin_with_free_delivery_fcfa"], 3450
        )

    def test_poids_et_collectes(self):
        result = self.simulate(
            weight_grams=3000, pickup_count=2
        )
        self.assertEqual(result["delivery_cost_fcfa"], 3300)

    def test_livraison_gratuite_rentable(self):
        result = self.simulate()
        self.assertTrue(result["free_delivery_eligible"])
        self.assertEqual(
            result["minimum_customer_delivery_fee_fcfa"], 0
        )

    def test_livraison_gratuite_non_rentable(self):
        result = self.simulate(
            supplier_cost_fcfa=19000
        )
        self.assertFalse(result["free_delivery_eligible"])
        self.assertEqual(
            result["margin_with_free_delivery_fcfa"], -2550
        )
        self.assertEqual(
            result["minimum_customer_delivery_fee_fcfa"], 4550
        )

    def test_donnees_invalides(self):
        with self.assertRaises(ValueError):
            self.simulate(pickup_count=0)
        with self.assertRaises(ValueError):
            self.simulate(distance_km=-2)
        with self.assertRaises(ValueError):
            self.simulate(weight_grams=-500)


    def test_forfait_identique_plusieurs_collectes(self):
        one = self.simulate(pickup_count=1)
        three = self.simulate(pickup_count=3)

        self.assertEqual(
            one["delivery_cost_fcfa"],
            three["delivery_cost_fcfa"],
        )
        self.assertEqual(
            one["delivery_cost_fcfa"], 3000
        )


    def test_ventilation_des_couts_p7(self):
        result = self.simulate(
            distance_km=5,
            weight_grams=3000,
            pickup_count=2,
        )

        self.assertEqual(result["moto_cost_fcfa"], 2000)
        self.assertEqual(
            result["weight_surcharge_fcfa"], 300
        )
        self.assertEqual(
            result["collection_cost_fcfa"], 1000
        )
        self.assertEqual(
            result["delivery_cost_fcfa"], 3300
        )

        total = (
            result["moto_cost_fcfa"]
            + result["weight_surcharge_fcfa"]
            + result["collection_cost_fcfa"]
        )

        self.assertEqual(
            total, result["delivery_cost_fcfa"]
        )

    def test_collectes_sans_surcout_p7(self):
        one = self.simulate(pickup_count=1)
        three = self.simulate(pickup_count=3)

        self.assertEqual(
            one["collection_cost_fcfa"], 1000
        )
        self.assertEqual(
            three["collection_cost_fcfa"], 1000
        )
        self.assertEqual(
            one["delivery_cost_fcfa"],
            three["delivery_cost_fcfa"],
        )
