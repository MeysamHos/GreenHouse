"""
auditlog/middleware.py

Injects the current request user into thread-local storage so that
audit signals know who triggered any model change — even when the
change happens inside a signal or helper that has no access to `request`.

Add to settings.py MIDDLEWARE (after AuthenticationMiddleware):

    'auditlog.middleware.AuditUserMiddleware',

IMPORTANT: must come AFTER django.contrib.auth.middleware.AuthenticationMiddleware
so that request.user is already populated when this middleware runs.
"""

from .signals import set_audit_user


class AuditUserMiddleware:
    """
    Sets the current authenticated user in thread-local storage
    at the start of every request, and clears it at the end.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set user before the view runs (and before any signals fire)
        user = getattr(request, 'user', None)
        set_audit_user(user)

        response = self.get_response(request)

        # Clear after response to avoid leaking between requests
        set_audit_user(None)

        return response
