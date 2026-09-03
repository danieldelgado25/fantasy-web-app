"""
app.py
======

Flask "application factory" — `create_app()` builds and returns a configured
Flask app rather than instantiating one at import time. This is the standard
Flask pattern for a reason that matters here specifically: it lets tests spin
up a fresh app instance (e.g. pointed at a test artifact path) without any
import-order side effects, and it lets `run.py` and a future WSGI server
(gunicorn, etc.) both create the app the same documented way.
"""

from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from wr_webapp.api.routes import api_bp


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO)

    app = Flask(__name__)

    # The React dev server runs on a different origin (localhost:5173) than
    # the Flask API (localhost:5000), so the browser's same-origin policy
    # blocks fetch() calls between them unless the API opts in via CORS.
    # Scoped to /api/* only — no reason to CORS-enable anything else.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(api_bp)

    return app
