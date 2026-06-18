"""
reports/views_template.py

Django template-based views (HTML responses).
Separate from views.py (DRF/JSON) — same pattern as other apps.
"""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date

from accounts.models import GreenhouseMembership
from greenhouse_app.models import Greenhouse, Bed, Crop
from operations.models import Operation
from inventory.models import InventoryItem
from . import queries


# ── Shared helper ─────────────────────────────────────────────────────────────

def _get_greenhouse(request, greenhouse_id):
    return get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )


def _parse_dates(request, default_days=30):
    date_to = parse_date(request.GET.get('to', '')) or date.today()
    date_from = parse_date(request.GET.get('from', '')) or (date_to - timedelta(days=default_days))
    return date_from, date_to


# ── Reports Index ─────────────────────────────────────────────────────────────

@login_required
def reports_index(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    membership = get_object_or_404(
        GreenhouseMembership,
        user=request.user,
        greenhouse=greenhouse,
    )

    return render(request, 'reports/index.html', {
        'greenhouse': greenhouse,
        'membership': membership,
        'breadcrumbs': [
            {'label': 'Greenhouses', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Reports', 'url': None},
        ],
    })


# ── Report 1: P&L Summary ─────────────────────────────────────────────────────

@login_required
def report_pnl(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    date_from, date_to = _parse_dates(request)

    data = queries.get_pnl_report(greenhouse, date_from, date_to)

    return render(request, 'reports/pnl.html', {
        'greenhouse': greenhouse,
        'date_from': date_from,
        'date_to': date_to,
        'data': data,
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'گزارش‌ها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/reports/'},
            {'label': 'خلاصه سود و زیان', 'url': None},
        ],
    })


# ── Report 2: Crop Lifecycle ──────────────────────────────────────────────────

@login_required
def report_crops(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    date_from, date_to = _parse_dates(request, default_days=365)
    crop_id = request.GET.get('crop_id', '')

    rows = queries.get_crop_report(
        greenhouse, date_from, date_to,
        crop_id=int(crop_id) if crop_id else None,
    )

    # Dropdown: all crops for this greenhouse
    all_crops = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
    ).order_by('crop_type', 'variety')

    return render(request, 'reports/crops.html', {
        'greenhouse': greenhouse,
        'date_from': date_from,
        'date_to': date_to,
        'rows': rows,
        'all_crops': all_crops,
        'selected_crop_id': crop_id,
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'گزارش‌ها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/reports/'},
            {'label': 'چرخه حیات محصول', 'url': None},
        ],
    })


# ── Report 3: Operations Log ──────────────────────────────────────────────────

@login_required
def report_operations(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    date_from, date_to = _parse_dates(request)

    op_type = request.GET.get('type', '')
    bed_id = request.GET.get('bed_id', '')

    data = queries.get_operations_report(
        greenhouse, date_from, date_to,
        operation_type=op_type or None,
        bed_id=int(bed_id) if bed_id else None,
    )

    # Dropdowns
    all_beds = Bed.objects.filter(
        house__greenhouse=greenhouse,
    ).select_related('house').order_by('house__name', 'code')

    return render(request, 'reports/operations.html', {
        'greenhouse': greenhouse,
        'date_from': date_from,
        'date_to': date_to,
        'data': data,
        'all_beds': all_beds,
        'selected_type': op_type,
        'selected_bed_id': bed_id,
        'operation_type_choices': Operation.Type.choices,
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'گزارش‌ها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/reports/'},
            {'label': 'گزارش عملیات', 'url': None},
        ],
    })


# ── Report 4: Inventory Usage ─────────────────────────────────────────────────

@login_required
def report_inventory(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    date_from, date_to = _parse_dates(request)
    category = request.GET.get('category', '')

    data = queries.get_inventory_report(
        greenhouse, date_from, date_to,
        category=category or None,
    )

    return render(request, 'reports/inventory.html', {
        'greenhouse': greenhouse,
        'date_from': date_from,
        'date_to': date_to,
        'data': data,
        'selected_category': category,
        'category_choices': InventoryItem.Category.choices,
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'گزارش‌ها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/reports/'},
            {'label': 'استفاده از انبار', 'url': None},
        ],
    })