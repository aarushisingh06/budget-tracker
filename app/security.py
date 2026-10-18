"""CSRF protection and security headers.

A tiny hand-rolled version of what Flask-WTF provides, to keep dependencies
minimal and show how it works: each session gets a random token, every form
includes it, and every state-changing request must send it back.
"""

import hmac
import secrets

from flask import abort, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def get_csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def init_app(app):
    app.jinja_env.globals["csrf_token"] = get_csrf_token

    @app.before_request
    def check_csrf():
        if not app.config.get("CSRF_ENABLED", True) or request.method in SAFE_METHODS:
            return
        sent = request.form.get("csrf_token", "")
        expected = session.get("_csrf", "")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, description="This form has expired. Reload the page and try again.")

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response
