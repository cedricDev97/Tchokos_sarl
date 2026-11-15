"""Calcul de marge contributive sur des coûts manuellement renseignés."""

from .models import OrderCostSheet
from sourcing.models import ProcurementLine

COST_FIELDS = ("courier_cost", "payment_fee", "other_cost")


def order_finance_summary(order):
    item_count = order.items.count()
    lines = list(
        ProcurementLine.objects.filter(order_item__order=order)
        .select_related("order_item", "supplier")
    )
    supplier_complete = (
        item_count > 0
        and len(lines) == item_count
        and all(
            line.supplier_id is not None
            and line.unit_cost is not None
            and line.status in {"confirmed", "collected"}
            for line in lines
        )
    )
    supplier_cost = (
        sum(line.unit_cost * line.order_item.qty for line in lines)
        if supplier_complete else None
    )
    sheet = OrderCostSheet.objects.filter(order=order).first()
    costs = {
        field: getattr(sheet, field) if sheet is not None else None
        for field in COST_FIELDS
    }
    costs_complete = all(v is not None for v in costs.values())
    calculable = supplier_complete and costs_complete
    closed = order.status == "delivered" and order.payment_state == "paid"
    margin = int(order.total) - supplier_cost - sum(costs.values()) if calculable else None
    return {
        "order_no": order.order_no,
        "order_status": order.status,
        "payment_status": order.payment_state,
        "subtotal": int(order.subtotal),
        "shipping_revenue": int(order.shipping_fee),
        "order_total": int(order.total),
        "supplier_cost": supplier_cost,
        "supplier_cost_complete": supplier_complete,
        "gross_product_margin": int(order.subtotal) - supplier_cost if supplier_complete else None,
        "costs": costs,
        "costs_complete": costs_complete,
        "margin_contribution": margin,
        "ready_for_closing": bool(calculable and closed),
        "status": "complete" if calculable and closed else "provisional" if calculable else "incomplete",
        "updated_at": sheet.updated_at.isoformat() if sheet is not None else None,
    }
