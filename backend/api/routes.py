from __future__ import annotations

from pathlib import Path

import polars as pl
from flask import Blueprint, jsonify, request

from wr_predictor.model import load_model, predict_next_week

"""
HTTP route definitions. This module only translates requests/responses —
it must not contain modeling or data-pipeline logic; that stays in
wr_predictor and gets imported here, not reimplemented here.
"""

# Blueprint groups all API routes under a shared "/api" prefix so app.py
# stays a pure wiring/configuration file.
api_blueprint = Blueprint("api", __name__, url_prefix="/api")

# Artifacts produced by backend/train.py. Gitignored and generated locally
# (or by a scheduled retraining job) — not committed to the repo.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = _BACKEND_ROOT / "models" / "wr_ridge.joblib"
SNAPSHOT_PATH = _BACKEND_ROOT / "data" / "processed" / "wr_latest_snapshot.parquet"
MODEL_VERSION = "ridge-v1"

_model = None
_feature_columns: list[str] | None = None
_snapshot: pl.DataFrame | None = None


def _load_artifacts() -> tuple | None:
    """
    Lazily load the trained model + player snapshot once per process and
    cache them. Returns None if train.py hasn't been run yet, so routes can
    respond with a clear 501 instead of crashing on a missing file.
    """
    global _model, _feature_columns, _snapshot
    if _model is None:
        if not MODEL_PATH.exists() or not SNAPSHOT_PATH.exists():
            return None
        _model, _feature_columns = load_model(str(MODEL_PATH))
        _snapshot = pl.read_parquet(SNAPSHOT_PATH)
    return _model, _feature_columns, _snapshot


@api_blueprint.route("/health", methods=["GET"])
def health() -> tuple[dict, int]:
    """Liveness check for uptime monitoring and local dev sanity checks."""
    return jsonify({"status": "ok"}), 200


@api_blueprint.route("/players", methods=["GET"])
def players() -> tuple[object, int]:
    """List every player with a current snapshot, for the frontend's search dropdown."""
    artifacts = _load_artifacts()
    if artifacts is None:
        return jsonify({"error": "not implemented", "detail": "no trained model artifact available yet"}), 501

    _, _, snapshot = artifacts
    rows = snapshot.select(["player_id", "player_display_name", "team"]).rename(
        {"player_display_name": "player_name"}
    )
    return jsonify(rows.to_dicts()), 200


@api_blueprint.route("/projections", methods=["GET"])
def projections() -> tuple[object, int]:
    """Serve a next-game PPR projection for one player, given ?player_id=...."""
    artifacts = _load_artifacts()
    if artifacts is None:
        return jsonify({"error": "not implemented", "detail": "no trained model artifact available yet"}), 501

    model, feature_columns, snapshot = artifacts
    player_id = request.args.get("player_id")
    if not player_id:
        return jsonify({"error": "bad request", "detail": "player_id query parameter is required"}), 400

    row = snapshot.filter(pl.col("player_id") == player_id)
    if row.is_empty():
        return jsonify({"error": "not found", "detail": f"no snapshot for player_id {player_id}"}), 404

    projected_points = predict_next_week(model, feature_columns, row)
    result = row.to_dicts()[0]
    return jsonify(
        {
            "player_id": result["player_id"],
            "player_name": result["player_display_name"],
            "team": result["team"],
            "opponent_team": result["opponent_team"],
            "season": result["season"],
            "week": result["week"],
            "projected_ppr_points": round(projected_points, 2),
            "model_version": MODEL_VERSION,
        }
    ), 200
