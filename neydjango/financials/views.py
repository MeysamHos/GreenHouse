"""
financials/views.py

DRF API views — returns JSON for Next.js frontend / mobile app.

Endpoints implemented:
  GET/POST   /api/v1/financials/sales/
  GET/PUT/DELETE /api/v1/financials/sales/<id>/
  GET/POST   /api/v1/financials/expenses/
  GET/PUT/DELETE /api/v1/financials/expenses/<id>/
  GET        /api/v1/reports/pnl/   ← the key document endpoint
"""

from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum, Count, Q
from django.utils.dateparse import parse_date
from accounts.permissions import IsGreenhouseOwnerOrManager 

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Sale, Expense
from .serializers import SaleSerializer, ExpenseSerializer, PnLReportSerializer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_greenhouse_or_403(request, greenhouse_id):
    """Return greenhouse if user is a member, else raise PermissionDenied."""
    from greenhouse_app.models import Greenhouse
    from accounts.models import GreenhouseMembership
    from rest_framework.exceptions import PermissionDenied, NotFound

    try:
        gh = Greenhouse.objects.get(id=greenhouse_id)
    except Greenhouse.DoesNotExist:
        raise NotFound('Greenhouse not found.')

    if not GreenhouseMembership.objects.filter(
        greenhouse=gh, user=request.user
    ).exists():
        raise PermissionDenied('You are not a member of this greenhouse.')
    return gh


# ── Sales ─────────────────────────────────────────────────────────────────────

class SaleListCreateView(generics.ListCreateAPIView):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from accounts.models import GreenhouseMembership
        accessible_ids = GreenhouseMembership.objects.filter(
            user=self.request.user
        ).values_list('greenhouse_id', flat=True)

        qs = Sale.objects.filter(greenhouse_id__in=accessible_ids).select_related(
            'crop', 'greenhouse', 'recorded_by'
        )

        # Filters
        gh_id = self.request.query_params.get('greenhouse_id')
        if gh_id:
            qs = qs.filter(greenhouse_id=gh_id)

        from_date = self.request.query_params.get('from')
        to_date = self.request.query_params.get('to')
        if from_date:
            qs = qs.filter(sold_at__gte=parse_date(from_date))
        if to_date:
            qs = qs.filter(sold_at__lte=parse_date(to_date))

        crop_id = self.request.query_params.get('crop_id')
        if crop_id:
            qs = qs.filter(crop_id=crop_id)

        status_filter = self.request.query_params.get('payment_status')
        if status_filter:
            qs = qs.filter(payment_status=status_filter)

        return qs


class SaleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from accounts.models import GreenhouseMembership
        accessible_ids = GreenhouseMembership.objects.filter(
            user=self.request.user
        ).values_list('greenhouse_id', flat=True)
        return Sale.objects.filter(greenhouse_id__in=accessible_ids)


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from accounts.models import GreenhouseMembership
        accessible_ids = GreenhouseMembership.objects.filter(
            user=self.request.user
        ).values_list('greenhouse_id', flat=True)

        qs = Expense.objects.filter(greenhouse_id__in=accessible_ids).select_related(
            'house', 'greenhouse', 'recorded_by'
        )

        gh_id = self.request.query_params.get('greenhouse_id')
        if gh_id:
            qs = qs.filter(greenhouse_id=gh_id)

        from_date = self.request.query_params.get('from')
        to_date = self.request.query_params.get('to')
        if from_date:
            qs = qs.filter(expense_date__gte=parse_date(from_date))
        if to_date:
            qs = qs.filter(expense_date__lte=parse_date(to_date))

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        return qs


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from accounts.models import GreenhouseMembership
        accessible_ids = GreenhouseMembership.objects.filter(
            user=self.request.user
        ).values_list('greenhouse_id', flat=True)
        return Expense.objects.filter(greenhouse_id__in=accessible_ids)


# ── P&L Report — the key endpoint from the business document ─────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pnl_report(request):
    """
    GET /api/v1/reports/pnl/?greenhouse_id=1&from=2024-01-01&to=2024-03-31&crop_id=5

    Computes P&L by aggregating:
      Revenue  = Sum of Sale.total_amount (quantity_kg × price_per_kg)
      Cost 1   = Sum of Operation.cost (variable field costs)
      Cost 2   = Sum of InventoryTransaction.unit_price × quantity for purchases
      Cost 3   = Sum of Expense.amount (overhead)

    Returns a breakdown by source plus top crops by revenue.
    """
    greenhouse_id = request.query_params.get('greenhouse_id') or request.query_params.get('greenhouse')
    from_str = request.query_params.get('from')
    to_str = request.query_params.get('to')
    crop_id = request.query_params.get('crop_id')

    if not greenhouse_id:
        return Response({'detail': 'greenhouse_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    gh = _get_greenhouse_or_403(request, greenhouse_id)

    # Explicit security role check executed before computing metrics
    from accounts.models import GreenhouseMembership
    membership = GreenhouseMembership.objects.filter(greenhouse=gh, user=request.user).first()
    
    if not membership or membership.role not in ['owner', 'manager']:
        return Response(
            {'detail': 'Only greenhouse Owners and Managers can perform this action.'}, 
            status=status.HTTP_403_FORBIDDEN
        )

    # Default to last 30 days if no date range given
    date_to = parse_date(to_str) if to_str else date.today()
    date_from = parse_date(from_str) if from_str else date_to - timedelta(days=30)

    # ── Revenue ──────────────────────────────────────────────────────
    from django.db.models import ExpressionWrapper, FloatField, F
    from django.db.models.functions import Coalesce

    sales_qs = Sale.objects.filter(
        greenhouse=gh,
        sold_at__range=(date_from, date_to),
    )
    if crop_id:
        sales_qs = sales_qs.filter(crop_id=crop_id)

    # Compute total_amount as quantity_kg * price_per_kg in DB
    from django.db.models import ExpressionWrapper, DecimalField
    revenue_agg = sales_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity_kg') * F('price_per_kg'),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        ),
        count=Count('id'),
    )
    total_revenue = revenue_agg['total'] or Decimal('0.00')
    sales_count = revenue_agg['count'] or 0

    # ── Cost 1: Operations ────────────────────────────────────────────
    from operations.models import Operation
    ops_qs = Operation.objects.filter(
        bed__house__greenhouse=gh,
        performed_at__range=(date_from, date_to),
        cost__isnull=False,
    )
    if crop_id:
        ops_qs = ops_qs.filter(crop_id=crop_id)
    cost_operations = ops_qs.aggregate(total=Sum('cost'))['total'] or Decimal('0.00')

    # ── Cost 2: Inventory Purchases ───────────────────────────────────
    from inventory.models import InventoryTransaction
    purchases_qs = InventoryTransaction.objects.filter(
        item__greenhouse=gh,
        transaction_type='purchase',
        performed_at__range=(date_from, date_to),
        unit_price__isnull=False,
    )
    cost_purchases = purchases_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity') * F('unit_price'),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        )
    )['total'] or Decimal('0.00')

    # ── Cost 3: Overhead Expenses ─────────────────────────────────────
    expenses_qs = Expense.objects.filter(
        greenhouse=gh,
        expense_date__range=(date_from, date_to),
    )
    cost_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ── Totals ────────────────────────────────────────────────────────
    total_cost = cost_operations + cost_purchases + cost_expenses
    gross_profit = total_revenue - total_cost
    margin = (
        (gross_profit / total_revenue * 100).quantize(Decimal('0.01'))
        if total_revenue > 0 else Decimal('0.00')
    )

    # ── Expense by category ───────────────────────────────────────────
    expense_breakdown = {}
    for row in expenses_qs.values('category').annotate(total=Sum('amount')):
        expense_breakdown[row['category']] = row['total']

    # ── Top crops by revenue ──────────────────────────────────────────
    top_crops = []
    crop_rev = sales_qs.values(
        'crop__id', 'crop__crop_type', 'crop__variety'
    ).annotate(
        revenue=Sum(
            ExpressionWrapper(
                F('quantity_kg') * F('price_per_kg'),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        )
    ).order_by('-revenue')[:5]

    for row in crop_rev:
        top_crops.append({
            'crop_id': row['crop__id'],
            'crop_type': row['crop__crop_type'],
            'variety': row['crop__variety'],
            'revenue': row['revenue'],
        })

    data = {
        'period_from': date_from,
        'period_to': date_to,
        'greenhouse_id': gh.id,
        'greenhouse_name': gh.name,
        'total_revenue': total_revenue,
        'total_sales_count': sales_count,
        'cost_operations': cost_operations,
        'cost_purchases': cost_purchases,
        'cost_expenses': cost_expenses,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'profit_margin_pct': margin,
        'expense_by_category': expense_breakdown,
        'top_crops_by_revenue': top_crops,
    }

    serializer = PnLReportSerializer(data)
    return Response(serializer.data)