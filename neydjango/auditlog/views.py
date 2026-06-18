"""
auditlog/views.py

Template views for the Audit Log — HTML pages for owners and managers.
Only OWNER and MANAGER roles can access these views.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date as _parse_date

from accounts.models import GreenhouseMembership
from greenhouse_app.models import Greenhouse
from .models import AuditLog


# ── Persian field label map ───────────────────────────────────────────────────
# Covers all tracked models: Operation, Crop, Bed, House, InventoryItem,
# InventoryTransaction, Sale, Expense, GreenhouseMembership, OperationPhoto

FIELD_LABELS_FA = {
    # Common
    'id':                   'شناسه',
    'created_at':           'تاریخ ایجاد',
    'updated_at':           'آخرین ویرایش',
    'notes':                'یادداشت',
    'is_active':            'فعال',

    # Operation
    'bed_id':               'بستر',
    'crop_id':              'کشت',
    'performed_by_id':      'انجام‌دهنده',
    'logged_by_id':         'ثبت‌کننده',
    'operation_type':       'نوع عملیات',
    'performed_at':         'تاریخ انجام',
    'quantity':             'مقدار',
    'unit':                 'واحد',
    'product_name':         'نام محصول/ماده',
    'product_batch':        'شماره بچ',
    'cost':                 'هزینه',
    'harvest_weight_kg':    'وزن برداشت (کیلوگرم)',
    'harvest_quality':      'کیفیت برداشت',

    # Crop
    'crop_type':            'نوع محصول',
    'variety':              'رقم/واریته',
    'status':               'وضعیت',
    'planted_at':           'تاریخ کاشت',
    'expected_harvest_at':  'تاریخ برداشت پیش‌بینی',
    'actual_harvest_at':    'تاریخ برداشت واقعی',
    'plant_count':          'تعداد بوته',

    # Bed
    'house_id':             'سالن',
    'code':                 'کد بستر',
    'area_m2':              'مساحت (متر مربع)',
    'capacity':             'ظرفیت',

    # House
    'greenhouse_id':        'گلخانه',
    'name':                 'نام',

    # InventoryItem
    'category':             'دسته‌بندی',
    'brand':                'برند',
    'description':          'توضیحات',
    'min_stock_threshold':  'حداقل موجودی هشدار',
    'unit_cost':            'هزینه واحد',
    'sku':                  'کد کالا',
    'created_by_id':        'ایجادکننده',

    # InventoryTransaction
    'item_id':              'آیتم انبار',
    'transaction_type':     'نوع تراکنش',
    'unit_price':           'قیمت واحد',
    'operation_id':         'عملیات مرتبط',
    'supplier_name':        'نام تامین‌کننده',
    'invoice_number':       'شماره فاکتور',
    'batch_number':         'شماره بچ',
    'expiry_date':          'تاریخ انقضا',
    'recorded_by_id':       'ثبت‌کننده',

    # Sale
    'buyer_name':           'نام خریدار',
    'buyer_phone':          'تلفن خریدار',
    'quantity_kg':          'مقدار (کیلوگرم)',
    'price_per_kg':         'قیمت هر کیلو',
    'payment_status':       'وضعیت پرداخت',
    'amount_paid':          'مبلغ پرداخت‌شده',
    'sold_at':              'تاریخ فروش',

    # Expense
    'amount':               'مبلغ',
    'expense_date':         'تاریخ هزینه',
    'vendor_name':          'نام فروشنده',

    # GreenhouseMembership
    'user_id':              'کاربر',
    'role':                 'نقش',
    'joined_at':            'تاریخ عضویت',
    'invited_by_id':        'دعوت‌کننده',

    # OperationPhoto
    'image':                'تصویر',
    'caption':              'توضیح تصویر',
    'uploaded_at':          'تاریخ آپلود',

}

# Fields whose values are stored as "YYYY-MM-DD" strings in the JSON diff.
# We parse them back to real date objects so to_jalali works in the template.
DATE_FIELDS = {
    'performed_at', 'planted_at', 'expected_harvest_at',
    'actual_harvest_at', 'sold_at', 'expense_date', 'expiry_date',
}


def _fa_label(field_name):
    """Return Persian label for a field name, or the raw name if not mapped."""
    return FIELD_LABELS_FA.get(field_name, field_name)


def _maybe_parse_date(field_name, value):
    """
    If this field is a known date field and value is a YYYY-MM-DD string,
    return a real date object so the to_jalali template filter can convert it.
    Otherwise return the value unchanged.
    """
    if field_name in DATE_FIELDS and isinstance(value, str) and len(value) == 10:
        parsed = _parse_date(value)
        if parsed:
            return parsed
    return value


# ── Permission helper ─────────────────────────────────────────────────────────

def _require_owner_or_manager(request, greenhouse):
    try:
        membership = GreenhouseMembership.objects.get(
            user=request.user,
            greenhouse=greenhouse,
        )
        if membership.role not in (
            GreenhouseMembership.Role.OWNER,
            GreenhouseMembership.Role.MANAGER,
        ):
            raise Http404
        return membership
    except GreenhouseMembership.DoesNotExist:
        raise Http404


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def audit_log_list(request, greenhouse_id):
    greenhouse = get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)
    membership = _require_owner_or_manager(request, greenhouse)

    qs = AuditLog.objects.filter(greenhouse=greenhouse).select_related('user')

    user_id     = request.GET.get('user_id', '').strip()
    action      = request.GET.get('action', '').strip()
    entity_type = request.GET.get('entity_type', '').strip()
    date_from   = request.GET.get('from', '').strip()
    date_to     = request.GET.get('to', '').strip()

    if user_id:
        qs = qs.filter(user_id=user_id)
    if action:
        qs = qs.filter(action=action)
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    paginator = Paginator(qs, 40)
    page_obj = paginator.get_page(request.GET.get('page'))

    members = GreenhouseMembership.objects.filter(
        greenhouse=greenhouse
    ).select_related('user').order_by('user__username')

    entity_types = (
        AuditLog.objects.filter(greenhouse=greenhouse)
        .values_list('entity_type', flat=True)
        .distinct()
        .order_by('entity_type')
    )

    context = {
        'greenhouse': greenhouse,
        'membership': membership,
        'page_obj': page_obj,
        'members': members,
        'entity_types': entity_types,
        'action_choices': AuditLog.Action.choices,
        'filter_user_id': user_id,
        'filter_action': action,
        'filter_entity_type': entity_type,
        'filter_from': date_from,
        'filter_to': date_to,
        'total_count': qs.count(),
    }
    return render(request, 'auditlog/audit_log_list.html', context)


@login_required
def audit_log_detail(request, greenhouse_id, log_id):
    greenhouse = get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)
    _require_owner_or_manager(request, greenhouse)

    entry = get_object_or_404(AuditLog, pk=log_id, greenhouse=greenhouse)

    diff_rows = []
    if entry.diff and isinstance(entry.diff, dict):
        if entry.action == AuditLog.Action.UPDATE:
            for field, change in entry.diff.items():
                before = _maybe_parse_date(field, change.get('before'))
                after  = _maybe_parse_date(field, change.get('after'))
                diff_rows.append({
                    'field':    _fa_label(field),
                    'field_raw': field,
                    'before':   before,
                    'after':    after,
                    'is_date':  field in DATE_FIELDS,
                })
        else:
            # CREATE or DELETE — flat key/value
            for field, value in entry.diff.items():
                value = _maybe_parse_date(field, value)
                diff_rows.append({
                    'field':    _fa_label(field),
                    'field_raw': field,
                    'value':    value,
                    'is_date':  field in DATE_FIELDS,
                })

    context = {
        'greenhouse': greenhouse,
        'entry': entry,
        'diff_rows': diff_rows,
        'is_update': entry.action == AuditLog.Action.UPDATE,
    }
    return render(request, 'auditlog/audit_log_detail.html', context)
