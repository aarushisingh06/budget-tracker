"""Budget Tracker: a small Flask app for tracking personal income and spending."""

import os
import secrets

from flask import Flask

from .money import format_cents


def create_app(test_config=None):
    """Application factory. Pass test_config to override settings in tests."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Set SECRET_KEY in the environment for stable sessions across restarts.
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "budget.sqlite"),
        CSRF_ENABLED=True,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2 MB upload limit for CSV imports
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db, routes, security

    db.init_app(app)
    security.init_app(app)
    app.register_blueprint(routes.bp)
    app.add_template_filter(format_cents, "money")

    with app.app_context():
        db.init_db()

    return app
