import re
import datetime
from django import template
from django.utils import timezone
import jdatetime

register = template.Library()


@register.filter
def to_jalali(value, fmt=None):
    """Convert a Gregorian date or datetime object to a Jalali string.

    If `value` is a timezone-aware datetime (e.g. created_at from
    auto_now_add), it must be converted to the local TIME_ZONE
    (Asia/Tehran) BEFORE extracting the date — otherwise a UTC
    datetime after 20:30 still belongs to "today" in Tehran, but
    naive date-extraction would show it as yesterday.
    """
    if not value:
        return ''
    try:
        # datetime.datetime is a subclass of datetime.date, so check
        # datetime first.
        if isinstance(value, datetime.datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)  # convert to settings.TIME_ZONE
            jd = jdatetime.date.fromgregorian(date=value.date())
        else:
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
