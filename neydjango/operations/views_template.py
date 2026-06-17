"""
operations/views_template.py — Django template HTML views
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django import forms
from django.utils import timezone
from django.http import JsonResponse

from inventory.models import InventoryItem, InventoryTransaction


from greenhouse_app.models import Greenhouse, House, Bed, Crop
from accounts.models import GreenhouseMembership
from .models import Operation, OperationPhoto


OPERATION_TO_INVENTORY_CATEGORY = {
    'fertilizing': 'fertilizer',
    'spraying':    'pesticide',
    'transplant':  'seed',
    'irrigation':  None,   # no inventory category — show all or none
    'harvesting':  'produce',
    'pruning':     None,
    'inspection':  None,
    'other':       None,
}

def _get_greenhouse_or_404(greenhouse_id, user):
    """Shared helper — ensures user is a member of the greenhouse."""
    return get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=user,
    )


# ── Operation Form ────────────────────────────────────────────────────────────

class OperationForm(forms.ModelForm):
    inventory_item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        required=False,
        label='Select from Inventory',
        help_text='Choose an inventory item to auto-fill product name and record consumption',
    )

    class Meta:
        model = Operation
        fields = [
            'bed', 'crop',
            'operation_type', 'performed_at',
            'inventory_item', 
            'quantity', 'unit',
            'product_name', 'product_batch',
            'cost',
            'harvest_weight_kg', 'harvest_quality',
            'notes',
            'performed_by',
        ]
        widgets = {
            'performed_at': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

        

    def __init__(self, *args, greenhouse=None, **kwargs):
        super().__init__(*args, **kwargs)
        if greenhouse:
            # Limit bed choices to this greenhouse only
            self.fields['bed'].queryset = Bed.objects.filter(
                house__greenhouse=greenhouse
            ).select_related('house')
            # Limit crop choices to active crops in this greenhouse
            self.fields['crop'].queryset = Crop.objects.filter(
                bed__house__greenhouse=greenhouse,
                status='growing',
            )
            # ← Populate inventory items for this greenhouse
            self.fields['inventory_item'].queryset = InventoryItem.objects.filter(
                greenhouse=greenhouse,
                is_active=True,
            ).order_by('category', 'name')

            # Limit performed_by to greenhouse members
            member_ids = GreenhouseMembership.objects.filter(
                greenhouse=greenhouse
            ).values_list('user_id', flat=True)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.fields['performed_by'].queryset = User.objects.filter(id__in=member_ids)
        # Set today as default date
        if not self.instance.pk:
            self.fields['performed_at'].initial = timezone.now().date()


# ── Operation List (per greenhouse) ───────────────────────────────────────────

@login_required
def operation_list(request, greenhouse_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)

    # Filters from query params
    op_type   = request.GET.get('type', '')
    bed_id    = request.GET.get('bed_id', '')
    from_date = request.GET.get('from', '')
    to_date   = request.GET.get('to', '')

    operations = Operation.objects.filter(
        bed__house__greenhouse=greenhouse
    ).select_related('bed', 'crop', 'performed_by').order_by('-performed_at', '-created_at')

    if op_type:
        operations = operations.filter(operation_type=op_type)
    if bed_id:
        operations = operations.filter(bed_id=bed_id)
    if from_date:
        operations = operations.filter(performed_at__gte=from_date)
    if to_date:
        operations = operations.filter(performed_at__lte=to_date)

    # Stats
    total_ops    = operations.count()
    total_cost   = sum(o.cost or 0 for o in operations)
    harvest_ops  = operations.filter(operation_type='harvesting')
    total_harvest = sum(o.harvest_weight_kg or 0 for o in harvest_ops)

    beds = Bed.objects.filter(house__greenhouse=greenhouse).select_related('house')

    return render(request, 'operations/operation_list.html', {
        'greenhouse':     greenhouse,
        'operations':     operations,
        'total_ops':      total_ops,
        'total_cost':     total_cost,
        'total_harvest':  total_harvest,
        'beds':           beds,
        'op_types':       Operation.Type.choices,
        # Current filter values (to keep form state)
        'filter_type':    op_type,
        'filter_bed':     bed_id,
        'filter_from':    from_date,
        'filter_to':      to_date,
    })


# ── Operation Detail ──────────────────────────────────────────────────────────

@login_required
def operation_detail(request, greenhouse_id, operation_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    operation  = get_object_or_404(
        Operation,
        id=operation_id,
        bed__house__greenhouse=greenhouse,
    )
    photos = operation.photos.all()

    return render(request, 'operations/operation_detail.html', {
        'greenhouse': greenhouse,
        'operation':  operation,
        'photos':     photos,
    })


# ── Operation Create ──────────────────────────────────────────────────────────

@login_required
def operation_create(request, greenhouse_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)

    # Pre-select bed if passed in query string (from bed detail page button)
    initial = {}
    bed_id = request.GET.get('bed_id')
    if bed_id:
        try:
            initial['bed'] = Bed.objects.get(id=bed_id, house__greenhouse=greenhouse)
            # Auto-select active crop for this bed
            active_crop = Crop.objects.filter(
                bed_id=bed_id, status='growing'
            ).first()
            if active_crop:
                initial['crop'] = active_crop
        except Bed.DoesNotExist:
            pass

    if request.method == 'POST':
        form = OperationForm(request.POST, greenhouse=greenhouse)
        if form.is_valid():
            operation = form.save(commit=False)
            operation.logged_by = request.user

            # If an inventory item was selected, auto-fill product_name
            inventory_item = form.cleaned_data.get('inventory_item')
            if inventory_item and not operation.product_name:
                operation.product_name = inventory_item.name

            operation.save()

            # Auto-create inventory transaction
            if inventory_item and form.cleaned_data.get('quantity'):
                from django.utils import timezone as tz
                if operation.operation_type in ('spraying', 'fertilizing', 'irrigation'):
                    tx_type = 'consumption'
                elif operation.operation_type == 'harvesting':
                    tx_type = 'harvest'
                else:
                    tx_type = None

                if tx_type:
                    InventoryTransaction.objects.create(
                        item=inventory_item,
                        transaction_type=tx_type,
                        quantity=form.cleaned_data['quantity'],
                        operation=operation,
                        performed_at=operation.performed_at,
                        recorded_by=request.user,
                        notes=f'Auto-recorded from operation #{operation.id}',
                    )

            # Handle photo uploads
            photos = request.FILES.getlist('photos')
            for photo in photos:
                OperationPhoto.objects.create(
                    operation=operation,
                    image=photo,
                    caption=request.POST.get('photo_caption', ''),
                )

            messages.success(
                request,
                f'{operation.get_operation_type_display()} logged.'
                + (f' {inventory_item.name} stock updated.' if inventory_item else '')
            )
            return redirect('operations:operation_list', greenhouse_id=greenhouse.id)
    else:
        form = OperationForm(greenhouse=greenhouse, initial=initial)

    return render(request, 'operations/operation_form.html', {
        'greenhouse': greenhouse,
        'form':       form,
        'form_title': 'ثبت عملیات جدید',
        'submit_label': 'ذخیره عملیات',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/operations/',
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'عملیات', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/operations/'},
            {'label': 'عملیات جدید', 'url': None},
        ],
    })


# ── Operation Edit ────────────────────────────────────────────────────────────

@login_required
def operation_edit(request, greenhouse_id, operation_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    operation  = get_object_or_404(
        Operation,
        id=operation_id,
        bed__house__greenhouse=greenhouse,
    )

    if request.method == 'POST':
        form = OperationForm(request.POST, instance=operation, greenhouse=greenhouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'عملیات بروزرسانی شد.')
            return redirect(
                'operations:operation_detail',
                greenhouse_id=greenhouse.id,
                operation_id=operation.id,
            )
    else:
        form = OperationForm(instance=operation, greenhouse=greenhouse)

    return render(request, 'operations/operation_form.html', {
        'greenhouse':   greenhouse,
        'form':         form,
        'operation':    operation,
        'form_title':   f'ویرایش: {operation.get_operation_type_display()}',
        'submit_label': 'ذخیره تغییرات',
        'cancel_url':   f'/greenhouse_app/greenhouses/{greenhouse.id}/operations/{operation.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'عملیات‌ها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/operations/'},
            {'label': 'ویرایش', 'url': None},
        ],
    })


# ── Operation Delete ──────────────────────────────────────────────────────────

@require_POST
@login_required
def operation_delete(request, greenhouse_id, operation_id):
    greenhouse = _get_greenhouse_or_404(greenhouse_id, request.user)
    operation  = get_object_or_404(
        Operation,
        id=operation_id,
        bed__house__greenhouse=greenhouse,
    )
    op_label = operation.get_operation_type_display()
    operation.delete()
    messages.success(request, f'عملیات {op_label} حذف شد.')
    return redirect('operations:operation_list', greenhouse_id=greenhouse.id)


# ── Operation Delete ──────────────────────────────────────────────────────────

def bed_crops_api(request, greenhouse_id, bed_id):
    """Returns active crops for a specific bed as JSON — used by the form JS."""
    from greenhouse_app.models import Crop
    crops = Crop.objects.filter(
        bed_id=bed_id,
        bed__house__greenhouse_id=greenhouse_id,
        status='growing',
    ).values('id', 'crop_type', 'variety')

    data = [
        {
            'id': c['id'],
            'label': f"{c['crop_type']}" + (f" ({c['variety']})" if c['variety'] else ''),
        }
        for c in crops
    ]
    return JsonResponse({'crops': data})


# ── Operation Inventory Dynamic field  ──────────────────────────────────────────────────────────


def inventory_items_by_type_api(request, greenhouse_id):
    """Returns inventory items filtered by operation type — used by form JS."""
    op_type  = request.GET.get('op_type', '')
    category = OPERATION_TO_INVENTORY_CATEGORY.get(op_type)

    qs = InventoryItem.objects.filter(
        greenhouse_id=greenhouse_id,
        is_active=True,
    )
    if category:
        qs = qs.filter(category=category)
    elif op_type:
        # operation type has no category mapping — return empty
        qs = qs.none()

    data = [
        {'id': item.id, 'name': item.name, 'unit': item.get_unit_display()}
        for item in qs.order_by('name')
    ]
    return JsonResponse({'items': data})