"""Simulation économique des livraisons eKAKO.

Tarifs indicatifs, non validés auprès des partenaires.
Aucune écriture en base et aucune action sur le checkout.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryTariff:
    base_fcfa: int = 1000
    per_km_fcfa: int = 200
    included_weight_grams: int = 2000
    extra_kg_fcfa: int = 300
    collection_flat_fcfa: int = 1000


def _nonnegative(name, value):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} doit être un entier positif ou nul.")


def simulate_delivery(
    *,
    product_revenue_fcfa: int,
    supplier_cost_fcfa: int,
    distance_km: int,
    weight_grams: int,
    pickup_count: int,
    payment_fee_fcfa: int,
    other_cost_fcfa: int,
    minimum_margin_fcfa: int,
    tariff: DeliveryTariff | None = None,
):
    """Retourne une simulation sans modifier les données eKAKO."""

    values = {
        "product_revenue_fcfa": product_revenue_fcfa,
        "supplier_cost_fcfa": supplier_cost_fcfa,
        "distance_km": distance_km,
        "weight_grams": weight_grams,
        "pickup_count": pickup_count,
        "payment_fee_fcfa": payment_fee_fcfa,
        "other_cost_fcfa": other_cost_fcfa,
        "minimum_margin_fcfa": minimum_margin_fcfa,
    }

    for name, value in values.items():
        _nonnegative(name, value)

    if pickup_count < 1:
        raise ValueError("Une collecte minimum est obligatoire.")

    if distance_km < 1:
        raise ValueError("Distance minimale : 1 km.")

    tariff = tariff or DeliveryTariff()

    for name, value in vars(tariff).items():
        _nonnegative(name, value)

    extra_grams = max(
        0, weight_grams - tariff.included_weight_grams
    )
    extra_kg = (extra_grams + 999) // 1000

    moto_cost = (
        tariff.base_fcfa
        + distance_km * tariff.per_km_fcfa
    )
    weight_surcharge = extra_kg * tariff.extra_kg_fcfa
    collection_cost = tariff.collection_flat_fcfa

    delivery_cost = (
        moto_cost + weight_surcharge + collection_cost
    )

    margin_free = (
        product_revenue_fcfa
        - supplier_cost_fcfa
        - delivery_cost
        - payment_fee_fcfa
        - other_cost_fcfa
    )

    min_customer_delivery_fee = max(
        0, minimum_margin_fcfa - margin_free
    )

    return {
        "moto_cost_fcfa": moto_cost,
        "weight_surcharge_fcfa": weight_surcharge,
        "collection_cost_fcfa": collection_cost,
        "delivery_cost_fcfa": delivery_cost,
        "margin_with_free_delivery_fcfa": margin_free,
        "minimum_margin_fcfa": minimum_margin_fcfa,
        "free_delivery_eligible": (
            margin_free >= minimum_margin_fcfa
        ),
        "minimum_customer_delivery_fee_fcfa": (
            min_customer_delivery_fee
        ),
        "estimated_margin_with_minimum_fee_fcfa": (
            margin_free + min_customer_delivery_fee
        ),
        "is_estimate": True,
    }
