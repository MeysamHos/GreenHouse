"""
financials/views_template.py

Django template-based views (HTML responses).
Separate from views.py (DRF/JSON) — same pattern as greenhouse_app.
"""

from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import require_POST
from django import forms
from django.utils.dateparse import parse_date

from accounts.models import GreenhouseMembership
from greenhouse_app.models import Greenhouse, Crop, House
from .models import Sale, Expense


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_greenhouse(request, greenhouse_id):
    return get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )


def _compute_pnl(greenhouse, date_from, date_to, crop_id=None):
    """
    Compute P&L dict for a greenhouse and date range.
    Shared by both the template and API views.
    """
    from operations.models import Operation
    from inventory.models import InventoryTransaction

    sales_qs = Sale.objects.filter(
        greenhouse=greenhouse,
        sold_at__range=(date_from, date_to),
    )
    if crop_id:
        sales_qs = sales_qs.filter(crop_id=crop_id)

    revenue_agg = sales_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity_kg') * F('price_per_kg'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        ),
        count=Count('id'),
    )
    total_revenue = revenue_agg['total'] or Decimal('0.00')

    ops_qs = Operation.objects.filter(
        bed__house__greenhouse=greenhouse,
        performed_at__range=(date_from, date_to),
        cost__isnull=False,
    )
    if crop_id:
        ops_qs = ops_qs.filter(crop_id=crop_id)
    cost_operations = ops_qs.aggregate(total=Sum('cost'))['total'] or Decimal('0.00')

    purchases_qs = InventoryTransaction.objects.filter(
        item__greenhouse=greenhouse,
        transaction_type='purchase',
        performed_at__range=(date_from, date_to),
        unit_price__isnull=False,
    )
    cost_purchases = purchases_qs.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('quantity') * F('unit_price'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
    )['total'] or Decimal('0.00')

    expenses_qs = Expense.objects.filter(
        greenhouse=greenhouse,
        expense_date__range=(date_from, date_to),
    )
    cost_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_cost = cost_operations + cost_purchases + cost_expenses
    gross_profit = total_revenue - total_cost
    margin = (
        (gross_profit / total_revenue * 100).quantize(Decimal('0.01'))
        if total_revenue > 0 else Decimal('0.00')
    )

    expense_breakdown = list(
        expenses_qs.values('category').annotate(total=Sum('amount')).order_by('-total')
    )

    top_crops = list(
        sales_qs.values('crop__crop_type', 'crop__variety').annotate(
            revenue=Sum(
                ExpressionWrapper(
                    F('quantity_kg') * F('price_per_kg'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        ).order_by('-revenue')[:5]
    )

    return {
        'total_revenue': total_revenue,
        'cost_operations': cost_operations,
        'cost_purchases': cost_purchases,
        'cost_expenses': cost_expenses,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'profit_margin_pct': margin,
        'expense_breakdown': expense_breakdown,
        'top_crops': top_crops,
        'sales_count': revenue_agg['count'] or 0,
    }


# ── Dashboard / P&L ──────────────────────────────────────────────────────────

@login_required
def financials_dashboard(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    # Date range from query params, default last 30 days
    to_str = request.GET.get('to', '')
    from_str = request.GET.get('from', '')
    crop_id = request.GET.get('crop_id', '')

    date_to = parse_date(to_str) if to_str else date.today()
    date_from = parse_date(from_str) if from_str else date_to - timedelta(days=30)

    pnl = _compute_pnl(
        greenhouse, date_from, date_to,
        crop_id=int(crop_id) if crop_id else None
    )

    # Recent sales for the table
    recent_sales = Sale.objects.filter(
        greenhouse=greenhouse,
        sold_at__range=(date_from, date_to),
    ).select_related('crop').order_by('-sold_at')[:10]

    # Recent expenses
    recent_expenses = Expense.objects.filter(
        greenhouse=greenhouse,
        expense_date__range=(date_from, date_to),
    ).order_by('-expense_date')[:10]

    # Crops for the filter dropdown
    active_crops = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
    ).order_by('crop_type', 'variety')

    return render(request, 'financials/dashboard.html', {
        'greenhouse': greenhouse,
        'date_from': date_from,
        'date_to': date_to,
        'selected_crop_id': crop_id,
        'pnl': pnl,
        'recent_sales': recent_sales,
        'recent_expenses': recent_expenses,
        'active_crops': active_crops,
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Financials', 'url': None},
        ],
    })


# ── Sales ─────────────────────────────────────────────────────────────────────

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            'crop', 'buyer_name', 'buyer_phone', 'product_name',
            'quantity_kg', 'price_per_kg', 'payment_status',
            'amount_paid', 'invoice_number', 'sold_at', 'notes',
        ]
        widgets = {
            'sold_at': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, greenhouse=None, **kwargs):
        super().__init__(*args, **kwargs)
        if greenhouse:
            self.fields['crop'].queryset = Crop.objects.filter(
                bed__house__greenhouse=greenhouse
            ).order_by('crop_type', 'variety')
            self.fields['crop'].required = False


@login_required
def sale_list(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    sales = Sale.objects.filter(greenhouse=greenhouse).select_related('crop').order_by('-sold_at')

    # Simple filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        sales = sales.filter(payment_status=status_filter)

    return render(request, 'financials/sale_list.html', {
        'greenhouse': greenhouse,
        'sales': sales,
        'status_filter': status_filter,
        'payment_status_choices': Sale.PaymentStatus.choices,
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Financials', 'url': f'/financials/{greenhouse.id}/'},
            {'label': 'Sales', 'url': None},
        ],
    })


@login_required
def sale_create(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    my_role = greenhouse.memberships.get(user=request.user).role
    if my_role not in (GreenhouseMembership.Role.OWNER, GreenhouseMembership.Role.MANAGER):
        messages.error(request, 'Only owners and managers can record sales.')
        return redirect('financials:sale_list', greenhouse_id=greenhouse.id)

    if request.method == 'POST':
        form = SaleForm(request.POST, greenhouse=greenhouse)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.greenhouse = greenhouse
            sale.recorded_by = request.user
            sale.save()
            messages.success(request, 'Sale recorded.')
            return redirect('financials:sale_list', greenhouse_id=greenhouse.id)
    else:
        form = SaleForm(greenhouse=greenhouse, initial={'sold_at': date.today()})

    return render(request, 'financials/form.html', {
        'form': form,
        'greenhouse': greenhouse,
        'form_title': 'Record Sale',
        'form_subtitle': 'Log produce sold to a buyer',
        'submit_label': 'Save Sale',
        'cancel_url': f'/financials/{greenhouse.id}/sales/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Sales', 'url': f'/financials/{greenhouse.id}/sales/'},
            {'label': 'New Sale', 'url': None},
        ],
    })


@login_required
def sale_edit(request, greenhouse_id, sale_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    sale = get_object_or_404(Sale, id=sale_id, greenhouse=greenhouse)

    if request.method == 'POST':
        form = SaleForm(request.POST, instance=sale, greenhouse=greenhouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sale updated.')
            return redirect('financials:sale_list', greenhouse_id=greenhouse.id)
    else:
        form = SaleForm(instance=sale, greenhouse=greenhouse)

    return render(request, 'financials/form.html', {
        'form': form,
        'greenhouse': greenhouse,
        'form_title': f'Edit Sale #{sale.id}',
        'submit_label': 'Save Changes',
        'delete_url': f'/financials/{greenhouse.id}/sales/{sale.id}/delete/',
        'cancel_url': f'/financials/{greenhouse.id}/sales/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Sales', 'url': f'/financials/{greenhouse.id}/sales/'},
            {'label': f'Edit #{sale.id}', 'url': None},
        ],
    })


@require_POST
@login_required
def sale_delete(request, greenhouse_id, sale_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    sale = get_object_or_404(Sale, id=sale_id, greenhouse=greenhouse)
    sale.delete()
    messages.success(request, 'Sale deleted.')
    return redirect('financials:sale_list', greenhouse_id=greenhouse.id)


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'category', 'description', 'amount', 'house',
            'expense_date', 'invoice_number', 'vendor_name', 'notes',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, greenhouse=None, **kwargs):
        super().__init__(*args, **kwargs)
        if greenhouse:
            self.fields['house'].queryset = House.objects.filter(greenhouse=greenhouse)
            self.fields['house'].required = False


@login_required
def expense_list(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    expenses = Expense.objects.filter(greenhouse=greenhouse).order_by('-expense_date')

    cat_filter = request.GET.get('category', '')
    if cat_filter:
        expenses = expenses.filter(category=cat_filter)

    return render(request, 'financials/expense_list.html', {
        'greenhouse': greenhouse,
        'expenses': expenses,
        'cat_filter': cat_filter,
        'category_choices': Expense.Category.choices,
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Financials', 'url': f'/financials/{greenhouse.id}/'},
            {'label': 'Expenses', 'url': None},
        ],
    })


@login_required
def expense_create(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, greenhouse=greenhouse)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.greenhouse = greenhouse
            expense.recorded_by = request.user
            expense.save()
            messages.success(request, 'Expense recorded.')
            return redirect('financials:expense_list', greenhouse_id=greenhouse.id)
    else:
        form = ExpenseForm(greenhouse=greenhouse, initial={'expense_date': date.today()})

    return render(request, 'financials/form.html', {
        'form': form,
        'greenhouse': greenhouse,
        'form_title': 'Record Expense',
        'form_subtitle': 'Log an overhead or operational cost',
        'submit_label': 'Save Expense',
        'cancel_url': f'/financials/{greenhouse.id}/expenses/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Expenses', 'url': f'/financials/{greenhouse.id}/expenses/'},
            {'label': 'New Expense', 'url': None},
        ],
    })


@login_required
def expense_edit(request, greenhouse_id, expense_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    expense = get_object_or_404(Expense, id=expense_id, greenhouse=greenhouse)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, greenhouse=greenhouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated.')
            return redirect('financials:expense_list', greenhouse_id=greenhouse.id)
    else:
        form = ExpenseForm(instance=expense, greenhouse=greenhouse)

    return render(request, 'financials/form.html', {
        'form': form,
        'greenhouse': greenhouse,
        'form_title': f'Edit Expense',
        'submit_label': 'Save Changes',
        'delete_url': f'/financials/{greenhouse.id}/expenses/{expense.id}/delete/',
        'cancel_url': f'/financials/{greenhouse.id}/expenses/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Expenses', 'url': f'/financials/{greenhouse.id}/expenses/'},
            {'label': 'Edit', 'url': None},
        ],
    })


@require_POST
@login_required
def expense_delete(request, greenhouse_id, expense_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    expense = get_object_or_404(Expense, id=expense_id, greenhouse=greenhouse)
    expense.delete()
    messages.success(request, 'Expense deleted.')
    return redirect('financials:expense_list', greenhouse_id=greenhouse.id)
