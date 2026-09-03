from __future__ import annotations

from flask import Blueprint, jsonify

"""
HTTP route definitions. This module only translates requests/responses —
it must not contain modeling or data-pipeline logic; that stays in
wr_predictor and gets imported here, not reimplemented here.
"""

# Blueprint groups all API routes under a shared "/api" prefix so app.py
# stays a pure wiring/configuration file.
api_blueprint = Blueprint("api", __name__, url_prefix="/api")


@api_blueprint.route("/health", methods=["GET"])
def health() -> tuple[dict, int]:
    """Liveness check for uptime monitoring and local dev sanity checks."""
    return jsonify({"status": "ok"}), 200


@api_blueprint.route("/projections", methods=["GET"])
def projections() -> tuple[dict, int]:
    """
    Placeholder for serving WR projections. Not wired to wr_predictor yet:
    model.py currently trains and evaluates in-memory only — there is no
    saved model artifact or single-row inference function for this route
    to call. Returns 501 until that persistence/inference layer exists.
    """
    return jsonify({"error": "not implemented", "detail": "no trained model artifact available yet"}), 501
