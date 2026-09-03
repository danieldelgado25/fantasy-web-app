"""
routes.py
=========

WHY ROUTES STAY THIN
-----------------------
Every handler here does the same three things, in order: (1) parse/validate
request params, (2) call a service function, (3) shape the result as JSON.
No feature engineering, no model calls, no pandas/polars manipulation happens
in this file — that all lives in services/. This split means the services are
independently testable/reusable (e.g. a future CLI or scheduled batch job
could call `projection_service.get_weekly_projections` without going through
HTTP at all), and this file stays readable as a map of "what the API offers"
without being cluttered by how each thing is computed.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from wr_webapp.services import model_service, projection_service
from wr_webapp.services.projection_service import ProjectionFilters

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/health")
def health():
    """Liveness check — used by deploy tooling / uptime monitors, and handy
    for confirming the model artifact actually loaded before you go poking
    at the other endpoints."""
    try:
        model_service.get_metadata()
        model_loaded = True
    except RuntimeError:
        model_loaded = False
    return jsonify({"status": "ok", "model_loaded": model_loaded})


@api_bp.get("/model-info")
def model_info():
    """Exposes training metadata (seasons trained on, chosen Ridge alpha,
    and — importantly — the baseline-vs-model comparison metrics) so the
    frontend (or a curious user hitting this URL directly) can see the model
    isn't a black box and can check whether it actually beats a naive
    rolling-average guess."""
    try:
        return jsonify(model_service.get_metadata())
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@api_bp.get("/projections")
def projections():
    """
    Weekly WR projections.

    Query params:
      season (int, required) - target season, e.g. 2024
      week   (int, required) - target week, e.g. 6
      team   (str, optional) - 3-letter team code to filter to, e.g. "SF"
      limit  (int, optional) - cap the number of rows returned

    Returns a JSON list of rows sorted by predicted_next_week_ppr descending.
    """
    season, week, error = _parse_season_week(request)
    if error:
        return error

    team = request.args.get("team") or None
    limit = request.args.get("limit", type=int)

    filters = ProjectionFilters(target_season=season, target_week=week, team=team, limit=limit)
    try:
        rows = projection_service.get_weekly_projections(filters)
    except RuntimeError as exc:
        # Model artifact missing — a deployment/config problem, not a bad request.
        return jsonify({"error": str(exc)}), 503

    return jsonify({
        "season": season,
        "week": week,
        "team": team,
        "count": len(rows),
        "projections": rows,
    })


@api_bp.get("/teams")
def teams():
    """Distinct team codes for a season, to populate the frontend's team
    filter dropdown dynamically instead of hardcoding a list."""
    season = request.args.get("season", type=int)
    if season is None:
        return jsonify({"error": "query param 'season' (int) is required"}), 400
    return jsonify({"season": season, "teams": projection_service.get_available_teams(season)})


def _parse_season_week(req):
    """Shared validation for the two required query params. Returns
    (season, week, None) on success or (None, None, error_response) on
    failure, so callers can `if error: return error` and move on."""
    season = req.args.get("season", type=int)
    week = req.args.get("week", type=int)
    if season is None or week is None:
        return None, None, (
            jsonify({"error": "query params 'season' and 'week' (both int) are required"}),
            400,
        )
    return season, week, None
