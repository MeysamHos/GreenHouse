"""
auditlog/apps.py
"""

from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditlog'
    verbose_name = 'Audit Log'

    def ready(self):
        """
        Called once when Django finishes loading all apps.
        This is the correct place to connect signals — all models are loaded by now.
        """
        from .signals import register_audit_signals
        register_audit_signals()
