"""
operations/template_actions.py  (NEW FILE)

Shared business logic for the three new actions: apply, cancel-remaining,
and skip. Both views.py (DRF/JSON) and views_template.py (HTML) call into
these functions, so behavior is identical regardless of how it's triggered —
the same pattern already used by reports/queries.py for report computation.

Three public functions:

  apply_template_to_crop(crop, user)
      Looks up the matching CropOperationTemplate (greenhouse-specific first,
      falling back to global), expands every step into dated Operation rows,
      and sets crop.applied_template. Raises TemplateActionError on any
      validation failure (already applied, crop not eligible, no matching
      template found) so callers can show a clear message either as a
      Django `messages.error()` or a DRF 400 response.

  cancel_remaining_planned(crop, user)
      Bulk-transitions every status='planned' Operation on this crop to
      status='cancelled'. Returns the count changed.

  skip_operation(operation, user)
      Transitions a single status='planned' Operation to status='skipped'.
      Raises TemplateActionError if the operation isn't currently planned.

IMPORTANT — audit log correctness:
  Every Operation created or modified here uses .save() individually
  (never bulk_create() or queryset.update()), because auditlog/signals.py
  connects to pre_save/post_save/post_delete — bulk operations would
  silently bypass the audit trail entirely. Operation is an explicitly
  tracked model (see auditlog/signals.py TRACKED_MODELS), so this matters.
"""

from datetime import timedelta

from django.db import transaction

from .models import Operation, CropOperationTemplate, CropOperationTemplateStep


class TemplateActionError(Exception):
    """Raised for any validation failure in apply/cancel/skip. Carries a
    human-readable message safe to show directly to the user."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Apply suggested operations
# ─────────────────────────────────────────────────────────────────────────────

def find_template_for_crop(crop):
    """
    Look up the CropOperationTemplate matching this crop's (crop_type, variety).

    Resolution order:
      1. Greenhouse-specific template for this exact greenhouse + crop_type
         + variety (is_active=True)
      2. Global template (greenhouse=None) for this crop_type + variety
         (is_active=True)

    A greenhouse-specific match, if found, is used INSTEAD of the global
    one — never merged. Returns None if no template matches either way.
    """
    greenhouse = crop.greenhouse  # property: bed.house.greenhouse

    specific = CropOperationTemplate.objects.filter(
        greenhouse=greenhouse,
        crop_type=crop.crop_type,
        variety=crop.variety,
        is_active=True,
    ).first()
    if specific:
        return specific

    return CropOperationTemplate.objects.filter(
        greenhouse__isnull=True,
        crop_type=crop.crop_type,
        variety=crop.variety,
        is_active=True,
    ).first()


def _expand_step_offsets(step: CropOperationTemplateStep):
    """
    Returns a list of integer day-offsets this step should generate
    Operations on, relative to planted_at.

    One-off step (repeat_every_days is None): a single-item list
    containing just day_offset_start.

    Recurring step: every day_offset_start, day_offset_start + N,
    day_offset_start + 2N, ... up to and including repeat_until_day.
    """
    if not step.repeat_every_days:
        return [step.day_offset_start]

    offsets = []
    day = step.day_offset_start
    while day <= step.repeat_until_day:
        offsets.append(day)
        day += step.repeat_every_days
    return offsets


def apply_template_to_crop(crop, user):
    """
    Applies the matching CropOperationTemplate to `crop`, generating
    real Operation rows (status=PLANNED, source=TEMPLATE).

    Eligibility (raises TemplateActionError if not met):
      - crop.status == 'growing'
      - crop.planted_at is set (required to compute real dates)
      - crop.applied_template is currently None (not already applied)
      - a matching template (specific or global) actually exists

    Returns the list of created Operation instances.
    """
    if crop.status != 'growing':
        raise TemplateActionError(
            'عملیات پیشنهادی فقط برای دوره‌های کشت «در حال رشد» قابل اعمال است.'
        )
    if not crop.planted_at:
        raise TemplateActionError(
            'تاریخ کاشت برای این دوره کشت ثبت نشده است؛ ابتدا تاریخ کاشت را وارد کنید.'
        )
    if crop.applied_template_id:
        raise TemplateActionError(
            f'عملیات پیشنهادی قبلاً برای این دوره کشت اعمال شده است '
            f'(قالب: «{crop.applied_template}»).'
        )

    template = find_template_for_crop(crop)
    if not template:
        raise TemplateActionError(
            f'هیچ قالب عملیات پیشنهادی برای «{crop.crop_type}'
            f'{" / " + crop.variety if crop.variety else ""}» یافت نشد.'
        )

    steps = template.steps.all()
    if not steps.exists():
        raise TemplateActionError(
            f'قالب «{template.name}» هیچ مرحله‌ای ندارد. لطفاً ابتدا مراحل را در پنل مدیریت تعریف کنید.'
        )

    created = []
    with transaction.atomic():
        for step in steps:
            for offset in _expand_step_offsets(step):
                performed_at = crop.planted_at + timedelta(days=offset - 1)
                # offset is 1-indexed ("day 1" = planting day itself),
                # so day 1 → +0 days, day 2 → +1 day, etc.

                operation = Operation(
                    bed=crop.bed,
                    crop=crop,
                    operation_type=step.operation_type,
                    performed_at=performed_at,
                    quantity=step.quantity,
                    unit=step.unit,
                    product_name=step.product_name,
                    notes=step.notes,
                    status=Operation.Status.PLANNED,
                    source=Operation.Source.TEMPLATE,
                    logged_by=user,
                    performed_by=None,
                    cost=None,
                )
                operation.save()  # individual .save() — required for audit log signals
                created.append(operation)

        crop.applied_template = template
        crop.save(update_fields=['applied_template', 'updated_at'])

    return created


# ─────────────────────────────────────────────────────────────────────────────
# Cancel remaining planned operations
# ─────────────────────────────────────────────────────────────────────────────

def cancel_remaining_planned(crop):
    """
    Transitions every status='planned' Operation belonging to `crop` to
    status='cancelled'. Uses an individual .save() per row (not
    queryset.update()) so each change is captured by the audit log.

    Returns the number of operations cancelled. Safe to call even if
    there are zero planned operations (returns 0, not an error).
    """
    planned_ops = Operation.objects.filter(crop=crop, status=Operation.Status.PLANNED)

    count = 0
    with transaction.atomic():
        for operation in planned_ops:
            operation.status = Operation.Status.CANCELLED
            operation.save(update_fields=['status', 'updated_at'])
            count += 1

    return count


# ─────────────────────────────────────────────────────────────────────────────
# Skip a single operation
# ─────────────────────────────────────────────────────────────────────────────

def skip_operation(operation):
    """
    Transitions a single Operation from status='planned' to status='skipped'.
    Raises TemplateActionError if the operation is not currently planned
    (e.g. already completed, already skipped, already cancelled).
    """
    if operation.status != Operation.Status.PLANNED:
        raise TemplateActionError(
            f'این عملیات در وضعیت «{operation.get_status_display()}» است '
            f'و فقط عملیات «برنامه‌ریزی شده» قابل رد کردن است.'
        )

    operation.status = Operation.Status.SKIPPED
    operation.save(update_fields=['status', 'updated_at'])
    return operation

# ─────────────────────────────────────────────────────────────────────────────
# Mark a single operation as completed (one-click)
# ─────────────────────────────────────────────────────────────────────────────

def complete_operation(operation, user):
    """
    Transitions a single Operation from status='planned' to
    status='completed', and sets performed_by to the user who clicked
    the button — since a one-click "mark as done" action is, in the
    common case, the operator confirming their own completed work.

    Raises TemplateActionError if the operation is not currently planned
    (e.g. already completed, skipped, or cancelled) — same gate as
    skip_operation.

    Does NOT touch cost, quantity, or any other field — those remain
    whatever the template step set (often null), editable afterward via
    the full edit form if the user wants to fill in more detail.
    """
    if operation.status != Operation.Status.PLANNED:
        raise TemplateActionError(
            f'این عملیات در وضعیت «{operation.get_status_display()}» است '
            f'و فقط عملیات «برنامه‌ریزی شده» قابل تکمیل کردن است.'
        )

    operation.status = Operation.Status.COMPLETED
    operation.performed_by = user
    operation.save(update_fields=['status', 'performed_by', 'updated_at'])
    return operation
