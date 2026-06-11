"""
reports/queries.py

All report computation lives here — pure functions that take a greenhouse
and a date range and return plain dicts/lists.

Both views.py (DRF/JSON) and views_template.py (HTML) call these functions
so the numbers are always identical regardless of how they're accessed.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField, Q
from django.db.models.functions import TruncMonth


# ── Shared helper ─────────────────────────────────────────────────────────────

def _revenue_expr():
    return ExpressionWrapper(
        F('quantity_kg') * F('price_per_kg'),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def _purchase_cost_expr():
    return ExpressionWrapper(
        F('quantity') * F('unit_price'),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


# ── Report 1: P&L Summary ─────────────────────────────────────────────────────

def get_pnl_report(greenhouse, date_from, date_to):
    """
    Full profit & loss for a greenhouse over a date range.
    Aggregates: Sales revenue, Operation costs, Inventory purchases, Overhead expenses.
    Returns a dict ready to pass to a template or serialize to JSON.
    """
    from financials.models import Sale, Expense
    from operations.models import Operation
    from inventory.models import InventoryTransaction

    # Revenue
    sales_qs = Sale.objects.filter(
        greenhouse=greenhouse,
        sold_at__range=(date_from, date_to),
    )
    rev = sales_qs.aggregate(
        total=Sum(_revenue_expr()),
        count=Count('id'),
    )
    total_revenue = rev['total'] or Decimal('0.00')
    sales_count = rev['count'] or 0

    # Cost: operations
    cost_ops = Operation.objects.filter(
        bed__house__greenhouse=greenhouse,
        performed_at__range=(date_from, date_to),
        cost__isnull=False,
    ).aggregate(total=Sum('cost'))['total'] or Decimal('0.00')

    # Cost: inventory purchases
    cost_purchases = InventoryTransaction.objects.filter(
        item__greenhouse=greenhouse,
        transaction_type='purchase',
        performed_at__range=(date_from, date_to),
        unit_price__isnull=False,
    ).aggregate(total=Sum(_purchase_cost_expr()))['total'] or Decimal('0.00')

    # Cost: overhead expenses
    expenses_qs = Expense.objects.filter(
        greenhouse=greenhouse,
        expense_date__range=(date_from, date_to),
    )
    cost_overhead = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_cost = cost_ops + cost_purchases + cost_overhead
    gross_profit = total_revenue - total_cost
    margin = (
        (gross_profit / total_revenue * 100).quantize(Decimal('0.01'))
        if total_revenue > 0 else Decimal('0.00')
    )

    # Expense breakdown by category
    expense_breakdown = list(
        expenses_qs.values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    # Monthly revenue trend (for chart)
    monthly_revenue = list(
        sales_qs.annotate(month=TruncMonth('sold_at'))
        .values('month')
        .annotate(total=Sum(_revenue_expr()))
        .order_by('month')
    )

    # Operations cost by type
    ops_by_type = list(
        Operation.objects.filter(
            bed__house__greenhouse=greenhouse,
            performed_at__range=(date_from, date_to),
            cost__isnull=False,
        )
        .values('operation_type')
        .annotate(total=Sum('cost'), count=Count('id'))
        .order_by('-total')
    )

    return {
        'total_revenue': total_revenue,
        'sales_count': sales_count,
        'cost_operations': cost_ops,
        'cost_purchases': cost_purchases,
        'cost_overhead': cost_overhead,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'profit_margin_pct': margin,
        'expense_breakdown': expense_breakdown,
        'monthly_revenue': monthly_revenue,
        'ops_by_type': ops_by_type,
    }


# ── Report 2: Crop Lifecycle ──────────────────────────────────────────────────

def get_crop_report(greenhouse, date_from, date_to, crop_id=None):
    """
    Per-crop profitability: cost, yield, revenue, profit margin.
    Covers all crops planted or active within the date range.
    """
    from greenhouse_app.models import Crop
    from operations.models import Operation
    from financials.models import Sale

    crops_qs = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
    ).filter(
        Q(planted_at__range=(date_from, date_to)) |
        Q(status='growing')
    ).select_related('bed__house')

    if crop_id:
        crops_qs = crops_qs.filter(id=crop_id)

    results = []
    for crop in crops_qs:
        # Operation costs for this crop
        op_cost = Operation.objects.filter(
            crop=crop,
            cost__isnull=False,
        ).aggregate(total=Sum('cost'))['total'] or Decimal('0.00')

        # Harvest weight from HARVESTING operations
        harvest_kg = Operation.objects.filter(
            crop=crop,
            operation_type='harvesting',
            harvest_weight_kg__isnull=False,
        ).aggregate(total=Sum('harvest_weight_kg'))['total'] or Decimal('0.00')

        # Revenue from sales
        revenue = Sale.objects.filter(crop=crop).aggregate(
            total=Sum(_revenue_expr())
        )['total'] or Decimal('0.00')

        # Operation count
        op_count = Operation.objects.filter(crop=crop).count()

        profit = revenue - op_cost
        margin = (
            (profit / revenue * 100).quantize(Decimal('0.01'))
            if revenue > 0 else Decimal('0.00')
        )
        cost_per_kg = (
            (op_cost / harvest_kg).quantize(Decimal('0.01'))
            if harvest_kg > 0 else None
        )

        results.append({
            'crop': crop,
            'op_cost': op_cost,
            'harvest_kg': harvest_kg,
            'revenue': revenue,
            'profit': profit,
            'margin_pct': margin,
            'op_count': op_count,
            'cost_per_kg': cost_per_kg,
        })

    # Sort by revenue descending
    results.sort(key=lambda x: x['revenue'], reverse=True)
    return results


# ── Report 3: Operations Log ──────────────────────────────────────────────────

def get_operations_report(greenhouse, date_from, date_to, operation_type=None, bed_id=None):
    """
    Filtered operation log with cost totals by type.
    Mirrors GET /api/v1/operations?from=&to=&type=&bed_id= from the business document.
    """
    from operations.models import Operation

    qs = Operation.objects.filter(
        bed__house__greenhouse=greenhouse,
        performed_at__range=(date_from, date_to),
    ).select_related('bed__house', 'crop', 'performed_by').order_by('-performed_at')

    if operation_type:
        qs = qs.filter(operation_type=operation_type)
    if bed_id:
        qs = qs.filter(bed_id=bed_id)

    # Summary aggregates
    summary = qs.aggregate(
        total_cost=Sum('cost'),
        total_count=Count('id'),
        avg_cost=Avg('cost'),
    )

    # Cost breakdown by operation type
    by_type = list(
        qs.values('operation_type')
        .annotate(count=Count('id'), total_cost=Sum('cost'))
        .order_by('-total_cost')
    )

    # Harvest totals
    harvest_total = qs.filter(
        operation_type='harvesting',
        harvest_weight_kg__isnull=False,
    ).aggregate(total_kg=Sum('harvest_weight_kg'))['total_kg'] or Decimal('0.00')

    return {
        'operations': qs,
        'total_cost': summary['total_cost'] or Decimal('0.00'),
        'total_count': summary['total_count'] or 0,
        'avg_cost': summary['avg_cost'],
        'by_type': by_type,
        'harvest_total_kg': harvest_total,
    }


# ── Report 4: Inventory Usage ─────────────────────────────────────────────────

def get_inventory_report(greenhouse, date_from, date_to, category=None):
    """
    Per-item consumption vs purchases over a period.
    Surfaces total spend per item and identifies highest-cost inputs.
    """
    from inventory.models import InventoryItem, InventoryTransaction

    items_qs = InventoryItem.objects.filter(
        greenhouse=greenhouse,
        is_active=True,
    )
    if category:
        items_qs = items_qs.filter(category=category)

    results = []
    for item in items_qs:
        txns = InventoryTransaction.objects.filter(
            item=item,
            performed_at__range=(date_from, date_to),
        )

        purchased = txns.filter(transaction_type='purchase').aggregate(
            qty=Sum('quantity'),
            cost=Sum(_purchase_cost_expr()),
        )
        consumed = txns.filter(transaction_type='consumption').aggregate(
            qty=Sum('quantity'),
        )
        wasted = txns.filter(transaction_type='waste').aggregate(
            qty=Sum('quantity'),
        )

        purchased_qty = purchased['qty'] or Decimal('0.000')
        purchased_cost = purchased['cost'] or Decimal('0.00')
        consumed_qty = consumed['qty'] or Decimal('0.000')
        wasted_qty = wasted['qty'] or Decimal('0.000')

        # Skip items with zero activity in period
        if purchased_qty == 0 and consumed_qty == 0:
            continue

        results.append({
            'item': item,
            'purchased_qty': purchased_qty,
            'purchased_cost': purchased_cost,
            'consumed_qty': consumed_qty,
            'wasted_qty': wasted_qty,
            'current_stock': item.current_stock(),
            'is_low_stock': item.is_low_stock,
        })

    # Sort by spend descending
    results.sort(key=lambda x: x['purchased_cost'], reverse=True)

    total_spend = sum(r['purchased_cost'] for r in results)

    return {
        'items': results,
        'total_spend': total_spend,
        'item_count': len(results),
    }
