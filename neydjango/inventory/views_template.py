"""
inventory/views_template.py — Django template HTML views
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django import forms
from django.utils import timezone
from decimal import Decimal

from greenhouse_app.models import Greenhouse
from .models import InventoryItem, InventoryTransaction


def _get_greenhouse_or_404(greenhouse_id, user):
    return get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=user,
    )


# ── Forms ─────────────────────────────────────────────────────────────────────

class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            'name', 'category', 'unit', 'brand',
            'description', 'min_stock_threshold', 'unit_cost',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class InventoryTransactionForm(forms.ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = [
            'transaction_type', 'quantity', 'unit_price',
            'supplier_name', 'invoice_number',
            'batch_number', 'expiry_date',
            'performed_at', 'notes',
        ]
        widgets = {
            'performed_at': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date':  forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['performed_at'].initial = timezone.now().date()


# ── Inventory List ─────────────────────────────────────────────────────────────

@login_required
def inventory_list(request, greenhouse_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)

    category_filter = request.GET.get('category', '')
    low_stock_filter = request.GET.get('low_stock', '')

    items = InventoryItem.objects.filter(
        greenhouse=greenhouse,
        is_active=True,
    ).order_by('category', 'name')

    if category_filter:
        items = items.filter(category=category_filter)

    # Attach current stock to each item
    for item in items:
        item.stock = item.current_stock()

    if low_stock_filter:
        items = [i for i in items if i.is_low_stock]

    # Stats
    all_items   = list(items)
    low_stock   = [i for i in all_items if i.is_low_stock]
    total_value = sum(
        (i.stock * Decimal(i.unit_cost)) for i in all_items
        if i.unit_cost and i.stock > 0
    )

    return render(request, 'inventory/inventory_list.html', {
        'greenhouse':      greenhouse,
        'items':           all_items,
        'low_stock_items': low_stock,
        'total_value':     total_value,
        'categories':      InventoryItem.Category.choices,
        'filter_category': category_filter,
        'filter_low_stock': low_stock_filter,
    })


# ── Item Detail ────────────────────────────────────────────────────────────────

@login_required
def inventory_item_detail(request, greenhouse_id, item_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    item = get_object_or_404(
        InventoryItem,
        id=item_id,
        greenhouse=greenhouse,
    )
    transactions = item.transactions.order_by('-performed_at', '-created_at')
    current_stock = item.current_stock()

    # Running balance for each transaction (for ledger view)
    running = []
    balance = current_stock
    for tx in transactions:
        if tx.transaction_type in ('purchase', 'adjustment_in', 'harvest'):
            running.append((tx, balance))
            balance -= tx.quantity
        else:
            running.append((tx, balance))
            balance += tx.quantity

    return render(request, 'inventory/inventory_item_detail.html', {
        'greenhouse':   greenhouse,
        'item':         item,
        'transactions': transactions,
        'running':      running,
        'current_stock': current_stock,
    })


# ── Item Create ────────────────────────────────────────────────────────────────

@login_required
def inventory_item_create(request, greenhouse_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)

    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.greenhouse  = greenhouse
            item.created_by  = request.user
            item.save()
            messages.success(request, f'"{item.name}" added to inventory.')
            return redirect('inventory:inventory_item_detail',
                            greenhouse_id=greenhouse.id, item_id=item.id)
    else:
        form = InventoryItemForm()

    return render(request, 'inventory/inventory_form.html', {
        'greenhouse':   greenhouse,
        'form':         form,
        'form_title':   'ایجاد آیتم در انبار',
        'submit_label': 'ایجاد آیتم',
        'cancel_url':   f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/',
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'انبار', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/'},
            {'label': 'آیتم جدید', 'url': None},
        ],
    })


# ── Item Edit ──────────────────────────────────────────────────────────────────

@login_required
def inventory_item_edit(request, greenhouse_id, item_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    item = get_object_or_404(InventoryItem, id=item_id, greenhouse=greenhouse)

    if request.method == 'POST':
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{item.name}" updated.')
            return redirect('inventory:inventory_item_detail',
                            greenhouse_id=greenhouse.id, item_id=item.id)
    else:
        form = InventoryItemForm(instance=item)

    return render(request, 'inventory/inventory_form.html', {
        'greenhouse':   greenhouse,
        'form':         form,
        'form_title':   f'ویرایش: {item.name}',
        'submit_label': 'ذخیره تغییرات',
        'cancel_url':   f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/{item.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'انبار', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/'},
            {'label': item.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/{item.id}/'},
            {'label': 'ویرایش', 'url': None},
        ],
    })


# ── Transaction Create ─────────────────────────────────────────────────────────

@login_required
def transaction_create(request, greenhouse_id, item_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    item = get_object_or_404(InventoryItem, id=item_id, greenhouse=greenhouse)

    # Pre-fill transaction type from query string
    initial = {}
    tx_type = request.GET.get('type', '')
    if tx_type:
        initial['transaction_type'] = tx_type

    if request.method == 'POST':
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.item        = item
            tx.recorded_by = request.user
            # Update item unit cost on purchases
            if tx.transaction_type == 'purchase' and tx.unit_price:
                item.unit_cost = tx.unit_price
                item.save()
            tx.save()
            messages.success(
                request,
                f'{tx.get_transaction_type_display()} of {tx.quantity} {item.get_unit_display()} recorded.'
            )
            return redirect('inventory:inventory_item_detail',
                            greenhouse_id=greenhouse.id, item_id=item.id)
    else:
        form = InventoryTransactionForm(initial=initial)

    return render(request, 'inventory/transaction_form.html', {
        'greenhouse':   greenhouse,
        'item':         item,
        'form':         form,
        'form_title':   f'ثبت تراکنش — {item.name}',
        'submit_label': 'ثبت تراکنش',
        'cancel_url':   f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/{item.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'انبار', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/'},
            {'label': item.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/inventory/{item.id}/'},
            {'label': 'تراکنش جدید', 'url': None},
        ],
    })


# ── Transaction Delete ─────────────────────────────────────────────────────────

@require_POST
@login_required
def transaction_delete(request, greenhouse_id, item_id, transaction_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    item = get_object_or_404(InventoryItem, id=item_id, greenhouse=greenhouse)
    tx   = get_object_or_404(InventoryTransaction, id=transaction_id, item=item)
    tx.delete()
    messages.success(request, 'Transaction deleted.')
    return redirect('inventory:inventory_item_detail',
                    greenhouse_id=greenhouse.id, item_id=item.id)
