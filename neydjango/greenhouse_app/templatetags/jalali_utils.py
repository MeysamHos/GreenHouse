import re
import datetime
from django import template
import jdatetime

register = template.Library()


# Same mapping as auditlog/views.py ENTITY_TYPE_LABELS_FA — kept in sync
# manually since this is a presentation-only concern for templates.
ENTITY_TYPE_LABELS_FA = {
    'Operation':             'عملیات',
    'OperationPhoto':        'تصویر عملیات',
    'InventoryItem':         'آیتم انبار',
    'InventoryTransaction':  'تراکنش انبار',
    'Sale':                  'فروش',
    'Expense':               'هزینه',
    'Crop':                  'کشت',
    'Bed':                   'بستر',
    'House':                 'سالن',
    'GreenhouseMembership':  'عضویت گلخانه',
}


@register.filter
def entity_type_fa(value):
    """Translate a model class name (e.g. 'Operation') to its Persian label."""
    return ENTITY_TYPE_LABELS_FA.get(value, value)


@register.filter
def to_jalali(value, fmt=None):
    """Convert a Gregorian date or datetime object to a Jalali string."""
    if not value:
        return ''
    try:
        jd = jdatetime.date.fromgregorian(date=value)
        return jd.strftime('%Y/%m/%d')
    except Exception:
        return str(value)


def _greg_str_to_jalali(date_str):
    """Convert a YYYY-MM-DD string to Jalali string. Returns original on failure."""
    try:
        greg = datetime.date.fromisoformat(date_str)
        return jdatetime.date.fromgregorian(date=greg).strftime('%Y/%m/%d')
    except Exception:
        return date_str


@register.filter
def jalali_text(value):
    """
    Scans a string for any YYYY-MM-DD pattern and replaces each one
    with its Jalali equivalent. Also replaces the English word ' on '
    (as used in Operation.__str__) with ' در '.

    Use this on entity_label in audit log templates so that entries
    saved before the __str__ fix still display Jalali dates.

    Example:
      "آبیاری @ گلخانه میثم / سالن اول / ردیف یک on 2026-06-18"
      →  "آبیاری @ گلخانه میثم / سالن اول / ردیف یک در 1405/03/28"
    """
    if not value:
        return value

    text = str(value)

    # Step 1: replace " on YYYY-MM-DD" → " در <jalali>"
    def replace_on_date(m):
        return 'در ' + _greg_str_to_jalali(m.group(1))

    text = re.sub(r'\bon\s+(\d{4}-\d{2}-\d{2})\b', replace_on_date, text)

    # Step 2: replace any remaining bare YYYY-MM-DD that survived step 1
    text = re.sub(r'\b(\d{4}-\d{2}-\d{2})\b',
                  lambda m: _greg_str_to_jalali(m.group(1)),
                  text)

    return text
