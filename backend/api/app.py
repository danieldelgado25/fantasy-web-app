from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from api.routes import api_blueprint

"""
Application factory. This file's only job is constructing and configuring
the Flask app (CORS, blueprints) — no routes or business logic live here,
so the wiring stays easy to find and the routes stay independently testable.
"""


def create_app() -> Flask:
    """Build and configure the Flask app instance."""
    app = Flask(__name__)

    # Frontend runs on a different origin (Vite dev server / Vercel domain),
    # so the browser needs CORS enabled to call this API.
    CORS(app)

    app.register_blueprint(api_blueprint)
    return app


if __name__ == "__main__":
    # Local dev entrypoint. Must run as a module so the `api.routes` import
    # resolves: `python -m api.app` from backend/.
    create_app().run(debug=True, port=5000)
