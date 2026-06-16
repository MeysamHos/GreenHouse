from django import template
import jdatetime

register = template.Library()

@register.filter
def to_jalali(value, fmt=None):
    """Convert a Gregorian date or datetime to Jalali string."""
    if not value:
        return ''
    try:
        jd = jdatetime.date.fromgregorian(date=value)
        return jd.strftime('%Y/%m/%d')
    except Exception:
        return str(value)