"""
auditlog/views.py

Template views for the Audit Log — HTML pages for owners and managers.
Only OWNER and MANAGER roles can access these views.

URL pattern (mounted in auditlog/urls.py):
  /greenhouse_app/greenhouses/<id>/audit/          — full log with filters
  /greenhouse_app/greenhouses/<id>/audit/<log_id>/ — single entry detail
"""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from accounts.models import GreenhouseMembership
from greenhouse_app.models import Greenhouse
from .models import AuditLog


# ── Permission helper ─────────────────────────────────────────────────────────

def _require_owner_or_manager(request, greenhouse):
    """Returns True if user is Owner or Manager, else raises Http404."""
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
    """
    Main audit log page — filterable, paginated table of all activity
    for a specific greenhouse.

    Filters (all optional, via GET params):
      ?user_id=      — filter by a specific team member
      ?action=       — create / update / delete
      ?entity_type=  — Operation / Sale / InventoryItem / etc.
      ?from=         — date range start (YYYY-MM-DD)
      ?to=           — date range end   (YYYY-MM-DD)
    """
    greenhouse = get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)
    membership = _require_owner_or_manager(request, greenhouse)

    qs = AuditLog.objects.filter(greenhouse=greenhouse).select_related('user')

    # ── Filters ───────────────────────────────────────────────────────
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

    # ── Pagination ────────────────────────────────────────────────────
    paginator = Paginator(qs, 40)
    page_obj = paginator.get_page(request.GET.get('page'))

    # ── Filter options for dropdowns ──────────────────────────────────
    # Members of this greenhouse (for "filter by user" dropdown)
    members = GreenhouseMembership.objects.filter(
        greenhouse=greenhouse
    ).select_related('user').order_by('user__username')

    # Distinct entity types that have logs in this greenhouse
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
        # Current filter values (to re-populate form)
        'filter_user_id': user_id,
        'filter_action': action,
        'filter_entity_type': entity_type,
        'filter_from': date_from,
        'filter_to': date_to,
        # Quick stats
        'total_count': qs.count(),
    }
    return render(request, 'auditlog/audit_log_list.html', context)


@login_required
def audit_log_detail(request, greenhouse_id, log_id):
    """
    Detail view for a single audit log entry.
    Shows the full diff in a readable before/after table.
    """
    greenhouse = get_object_or_404(Greenhouse, pk=greenhouse_id, is_active=True)
    _require_owner_or_manager(request, greenhouse)

    entry = get_object_or_404(AuditLog, pk=log_id, greenhouse=greenhouse)

    # Parse diff into a list of (field, before, after) for the template
    diff_rows = []
    if entry.diff and isinstance(entry.diff, dict):
        if entry.action == AuditLog.Action.UPDATE:
            for field, change in entry.diff.items():
                diff_rows.append({
                    'field': field,
                    'before': change.get('before'),
                    'after': change.get('after'),
                })
        else:
            # CREATE or DELETE — flat key/value
            for field, value in entry.diff.items():
                diff_rows.append({
                    'field': field,
                    'value': value,
                })

    context = {
        'greenhouse': greenhouse,
        'entry': entry,
        'diff_rows': diff_rows,
        'is_update': entry.action == AuditLog.Action.UPDATE,
    }
    return render(request, 'auditlog/audit_log_detail.html', context)
