"""
reports/views.py

DRF API views — returns JSON for Next.js frontend / mobile app.

All heavy lifting is delegated to queries.py so the numbers
are identical whether accessed via HTML or API.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from . import queries


# ── Shared helper ─────────────────────────────────────────────────────────────

def _resolve(request, greenhouse_id):
    """Return greenhouse if user is a member, else raise."""
    from greenhouse_app.models import Greenhouse
    from accounts.models import GreenhouseMembership

    try:
        gh = Greenhouse.objects.get(id=greenhouse_id)
    except Greenhouse.DoesNotExist:
        raise NotFound('Greenhouse not found.')
    if not GreenhouseMembership.objects.filter(greenhouse=gh, user=request.user).exists():
        raise PermissionDenied('Not a member of this greenhouse.')
    return gh


def _dates(request, default_days=30):
    """Parse from/to from query params with a sensible default."""
    date_to = parse_date(request.query_params.get('to', '')) or date.today()
    date_from = parse_date(request.query_params.get('from', '')) or (date_to - timedelta(days=default_days))
    return date_from, date_to


# ── P&L Summary API ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_pnl(request, greenhouse_pk):
    gh = _resolve(request, greenhouse_pk)
    date_from, date_to = _dates(request)
    data = queries.get_pnl_report(gh, date_from, date_to)

    # Serialise Decimal and date objects for JSON
    def _d(v):
        return float(v) if isinstance(v, Decimal) else v

    return Response({
        'greenhouse_id': gh.id,
        'greenhouse_name': gh.name,
        'period_from': date_from,
        'period_to': date_to,
        'total_revenue': _d(data['total_revenue']),
        'sales_count': data['sales_count'],
        'cost_operations': _d(data['cost_operations']),
        'cost_purchases': _d(data['cost_purchases']),
        'cost_overhead': _d(data['cost_overhead']),
        'total_cost': _d(data['total_cost']),
        'gross_profit': _d(data['gross_profit']),
        'profit_margin_pct': _d(data['profit_margin_pct']),
        'expense_breakdown': [
            {'category': r['category'], 'total': _d(r['total'])}
            for r in data['expense_breakdown']
        ],
        'ops_by_type': [
            {'type': r['operation_type'], 'count': r['count'], 'total_cost': _d(r['total_cost'] or 0)}
            for r in data['ops_by_type']
        ],
        'monthly_revenue': [
            {'month': str(r['month'])[:7], 'total': _d(r['total'])}
            for r in data['monthly_revenue']
        ],
    })


# ── Crop Lifecycle API ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_crop_report(request, greenhouse_pk):
    gh = _resolve(request, greenhouse_pk)
    date_from, date_to = _dates(request, default_days=365)
    crop_id = request.query_params.get('crop_id')

    rows = queries.get_crop_report(gh, date_from, date_to, crop_id=crop_id)

    def _d(v):
        return float(v) if isinstance(v, Decimal) else v

    return Response({
        'greenhouse_id': gh.id,
        'period_from': date_from,
        'period_to': date_to,
        'crops': [
            {
                'crop_id': r['crop'].id,
                'crop_type': r['crop'].crop_type,
                'variety': r['crop'].variety,
                'status': r['crop'].status,
                'bed': str(r['crop'].bed),
                'planted_at': r['crop'].planted_at,
                'op_count': r['op_count'],
                'op_cost': _d(r['op_cost']),
                'harvest_kg': _d(r['harvest_kg']),
                'revenue': _d(r['revenue']),
                'profit': _d(r['profit']),
                'margin_pct': _d(r['margin_pct']),
                'cost_per_kg': _d(r['cost_per_kg']) if r['cost_per_kg'] else None,
            }
            for r in rows
        ],
    })


# ── Operations Report API ─────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_operations_report(request, greenhouse_pk):
    gh = _resolve(request, greenhouse_pk)
    date_from, date_to = _dates(request)
    op_type = request.query_params.get('type')
    bed_id = request.query_params.get('bed_id')

    data = queries.get_operations_report(gh, date_from, date_to,
                                         operation_type=op_type, bed_id=bed_id)

    def _d(v):
        return float(v) if isinstance(v, Decimal) else v

    return Response({
        'greenhouse_id': gh.id,
        'period_from': date_from,
        'period_to': date_to,
        'total_count': data['total_count'],
        'total_cost': _d(data['total_cost']),
        'harvest_total_kg': _d(data['harvest_total_kg']),
        'by_type': [
            {'type': r['operation_type'], 'count': r['count'],
             'total_cost': _d(r['total_cost'] or 0)}
            for r in data['by_type']
        ],
        'operations': [
            {
                'id': op.id,
                'date': op.performed_at,
                'type': op.operation_type,
                'bed': str(op.bed),
                'crop': str(op.crop) if op.crop else None,
                'product': op.product_name,
                'quantity': float(op.quantity) if op.quantity else None,
                'unit': op.unit,
                'cost': float(op.cost) if op.cost else None,
                'harvest_kg': float(op.harvest_weight_kg) if op.harvest_weight_kg else None,
            }
            for op in data['operations'][:200]   # cap at 200 for API
        ],
    })


# ── Inventory Usage API ───────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_inventory_report(request, greenhouse_pk):
    gh = _resolve(request, greenhouse_pk)
    date_from, date_to = _dates(request)
    category = request.query_params.get('category')

    data = queries.get_inventory_report(gh, date_from, date_to, category=category)

    def _d(v):
        return float(v) if isinstance(v, Decimal) else v

    return Response({
        'greenhouse_id': gh.id,
        'period_from': date_from,
        'period_to': date_to,
        'total_spend': _d(data['total_spend']),
        'item_count': data['item_count'],
        'items': [
            {
                'item_id': r['item'].id,
                'name': r['item'].name,
                'category': r['item'].category,
                'unit': r['item'].unit,
                'purchased_qty': _d(r['purchased_qty']),
                'purchased_cost': _d(r['purchased_cost']),
                'consumed_qty': _d(r['consumed_qty']),
                'wasted_qty': _d(r['wasted_qty']),
                'current_stock': _d(r['current_stock']),
                'is_low_stock': r['is_low_stock'],
            }
            for r in data['items']
        ],
    })
