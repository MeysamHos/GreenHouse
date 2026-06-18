"""
auditlog/signals.py

Central signal handler that automatically writes an AuditLog entry for every
tracked model change. No individual view needs to call anything — connecting
signals in apps.py is all that's needed.

HOW IT WORKS:
  1. apps.py calls register_audit_signals() in its ready() method.
  2. register_audit_signals() connects post_save and post_delete signals
     for every model listed in TRACKED_MODELS.
  3. Each signal handler resolves the greenhouse the record belongs to,
     extracts a diff (for updates), and writes an AuditLog entry.

THREAD LOCAL:
  We use a threading.local() to carry the current request user into the
  signal. Views must call set_audit_user(request.user) (done via middleware)
  so signals know who triggered the change.

DIFF EXTRACTION:
  For UPDATE signals, we compare the current DB state to the new values
  using model._loaded_values (stored on post_init) vs the current field values.
  Fields excluded from diff: auto timestamps, large text blobs, binary data.
"""

import json
import threading
from decimal import Decimal
from datetime import date, datetime

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

_thread_locals = threading.local()


def set_audit_user(user):
    """Call this with request.user to make the audit logger aware of who's acting."""
    _thread_locals.user = user


def get_audit_user():
    return getattr(_thread_locals, 'user', None)


# ── Fields excluded from diff capture ────────────────────────────────────────

EXCLUDED_FIELDS = {
    'created_at', 'updated_at', 'uploaded_at', 'joined_at',
    'password', 'last_login', 'date_joined',
}

# Large text fields we don't want to store entire contents of
TRUNCATED_FIELDS = {'notes', 'description', 'location_geojson', 'diff'}


def _serialize_value(val):
    """Convert a field value to a JSON-serialisable type."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float, str)):
        return val
    return str(val)


def _model_to_dict(instance, exclude=None):
    """Return a flat dict of field_name → serialised value for an instance."""
    exclude = exclude or set()
    result = {}
    for field in instance._meta.concrete_fields:
        name = field.attname  # e.g. 'bed_id' for ForeignKeys
        if name in EXCLUDED_FIELDS or name in exclude:
            continue
        val = getattr(instance, name, None)
        if name in TRUNCATED_FIELDS and isinstance(val, str) and len(val) > 200:
            val = val[:200] + '…'
        result[name] = _serialize_value(val)
    return result


def _compute_diff(old_values, new_instance):
    """Compare old dict to current instance fields. Returns changed fields only."""
    diff = {}
    for field in new_instance._meta.concrete_fields:
        name = field.attname
        if name in EXCLUDED_FIELDS:
            continue
        new_val = _serialize_value(getattr(new_instance, name, None))
        old_val = old_values.get(name)
        if new_val != old_val:
            diff[name] = {'before': old_val, 'after': new_val}
    return diff


# ── Greenhouse resolver ───────────────────────────────────────────────────────

def _resolve_greenhouse(instance):
    """
    Walk the model's relations to find the Greenhouse this instance belongs to.
    Returns a Greenhouse instance or None.
    """
    # Direct greenhouse FK
    if hasattr(instance, 'greenhouse_id') and instance.greenhouse_id:
        try:
            from greenhouse_app.models import Greenhouse
            return Greenhouse.objects.get(pk=instance.greenhouse_id)
        except Exception:
            pass

    # Via bed → house → greenhouse
    if hasattr(instance, 'bed_id') and instance.bed_id:
        try:
            from greenhouse_app.models import Bed
            return Bed.objects.select_related('house__greenhouse').get(
                pk=instance.bed_id
            ).house.greenhouse
        except Exception:
            pass

    # Via operation → bed → house → greenhouse
    if hasattr(instance, 'operation_id') and instance.operation_id:
        try:
            from operations.models import Operation
            op = Operation.objects.select_related('bed__house__greenhouse').get(
                pk=instance.operation_id
            )
            return op.bed.house.greenhouse
        except Exception:
            pass

    # Via item → greenhouse (InventoryTransaction)
    if hasattr(instance, 'item_id') and instance.item_id:
        try:
            from inventory.models import InventoryItem
            item = InventoryItem.objects.select_related('greenhouse').get(
                pk=instance.item_id
            )
            return item.greenhouse
        except Exception:
            pass

    # Via house → greenhouse
    if hasattr(instance, 'house_id') and instance.house_id:
        try:
            from greenhouse_app.models import House
            return House.objects.select_related('greenhouse').get(
                pk=instance.house_id
            ).greenhouse
        except Exception:
            pass

    return None


# ── Pre-save: capture old values before the save ─────────────────────────────

def _handle_pre_save(sender, instance, **kwargs):
    """Store the current DB values on the instance before saving, for diff computation."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._pre_save_values = _model_to_dict(old)
        except sender.DoesNotExist:
            instance._pre_save_values = None
    else:
        instance._pre_save_values = None


# ── Post-save: write the AuditLog entry ──────────────────────────────────────

def _handle_post_save(sender, instance, created, **kwargs):
    """Write CREATE or UPDATE audit log entry after a save."""
    try:
        from auditlog.models import AuditLog

        user = get_audit_user()
        greenhouse = _resolve_greenhouse(instance)
        entity_type = sender.__name__

        if created:
            action = AuditLog.Action.CREATE
            diff = _model_to_dict(instance)
        else:
            action = AuditLog.Action.UPDATE
            old_values = getattr(instance, '_pre_save_values', None) or {}
            diff = _compute_diff(old_values, instance)
            if not diff:
                return  # nothing actually changed — skip

        AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            username_snapshot=str(user) if user else '',
            greenhouse=greenhouse,
            action=action,
            entity_type=entity_type,
            entity_id=instance.pk,
            entity_label=str(instance)[:300],
            diff=diff,
        )
    except Exception:
        pass  # Never let audit logging crash the main request


# ── Post-delete: write the AuditLog entry ────────────────────────────────────

def _handle_post_delete(sender, instance, **kwargs):
    """Write DELETE audit log entry after a deletion."""
    try:
        from auditlog.models import AuditLog

        user = get_audit_user()
        greenhouse = _resolve_greenhouse(instance)

        AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            username_snapshot=str(user) if user else '',
            greenhouse=greenhouse,
            action=AuditLog.Action.DELETE,
            entity_type=sender.__name__,
            entity_id=instance.pk,
            entity_label=str(instance)[:300],
            diff=_model_to_dict(instance),
        )
    except Exception:
        pass


# ── Registration ──────────────────────────────────────────────────────────────

# Maps model path string → (sender class, connect signals)
TRACKED_MODELS = [
    'operations.Operation',
    'operations.OperationPhoto',
    'inventory.InventoryItem',
    'inventory.InventoryTransaction',
    'financials.Sale',
    'financials.Expense',
    'greenhouse_app.Crop',
    'greenhouse_app.Bed',
    'greenhouse_app.House',
    'accounts.GreenhouseMembership',
]


def register_audit_signals():
    """
    Called from AuditlogConfig.ready() — connects signals for all tracked models.
    Using Django's app registry avoids circular import issues at module load time.
    """
    from django.apps import apps

    for model_path in TRACKED_MODELS:
        app_label, model_name = model_path.split('.')
        try:
            model = apps.get_model(app_label, model_name)
            pre_save.connect(_handle_pre_save, sender=model, weak=False)
            post_save.connect(_handle_post_save, sender=model, weak=False)
            post_delete.connect(_handle_post_delete, sender=model, weak=False)
        except LookupError:
            pass  # App not installed yet — silently skip
