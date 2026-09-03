"""
model_service.py
=================

WHY A SEPARATE SERVICE FOR THIS
---------------------------------
Loading a model artifact from disk (unpickling a fitted sklearn Pipeline) is
comparatively expensive and should happen exactly once per process, not once
per HTTP request. This module owns that lifecycle: load-on-first-use, cache
in a module-level singleton, and expose a small, stable interface
(`predict`, `get_metadata`) to the rest of the app.

Nothing outside this file should ever call `joblib.load` directly or reach
into the artifact dict's raw keys — if we later switch from a single joblib
file to, say, an MLflow model registry, only this file needs to change.

WHAT'S IN THE ARTIFACT
-------------------------
See training/train_model.py for how this is built. It's a dict:
  - "model": fitted sklearn Pipeline (StandardScaler + Ridge)
  - "feature_cols": exact ordered list of columns the model expects as input
  - "target_col": "next_week_ppr_points"
  - "metrics": ridge vs. baseline metrics from training, for transparency
  - plus training metadata (seasons used, chosen alpha, timestamp)

The `feature_cols` list matters more than it might look like: sklearn
Pipelines predict based on column *position*, not name. If the serving code
ever builds a DataFrame with columns in a different order (or missing one),
predictions would be silently wrong rather than erroring. `predict()` below
guards against that by explicitly selecting/reordering columns before calling
the model, and raising if any are missing.
"""

from __future__ import annotations

import threading
from typing import Any

import joblib
import pandas as pd

from wr_webapp.config import ARTIFACT_PATH

_artifact: dict[str, Any] | None = None
_load_lock = threading.Lock()


def _load_artifact() -> dict[str, Any]:
    global _artifact
    if _artifact is not None:
        return _artifact

    with _load_lock:
        # Re-check inside the lock: another thread may have loaded it while
        # we were waiting (classic double-checked locking for a singleton).
        if _artifact is None:
            if not ARTIFACT_PATH.exists():
                raise RuntimeError(
                    f"No trained model artifact found at {ARTIFACT_PATH}. "
                    "Run `python training/train_model.py` from backend/ first."
                )
            _artifact = joblib.load(ARTIFACT_PATH)
    return _artifact


def get_metadata() -> dict[str, Any]:
    """Everything about the loaded model EXCEPT the model object itself —
    safe to serialize straight into an API response (see /api/model-info)."""
    artifact = _load_artifact()
    return {k: v for k, v in artifact.items() if k != "model"}


def get_feature_cols() -> list[str]:
    return list(_load_artifact()["feature_cols"])


def predict(features: pd.DataFrame) -> pd.Series:
    """
    Run the trained model on a feature DataFrame.

    `features` must contain (at least) every column in `feature_cols`; extra
    columns (e.g. player_display_name, team — identifying info the model was
    never trained on) are fine and ignored, since we explicitly select and
    order the modeling columns before calling `.predict()`.
    """
    artifact = _load_artifact()
    feature_cols = artifact["feature_cols"]

    missing = [c for c in feature_cols if c not in features.columns]
    if missing:
        raise ValueError(
            f"Feature DataFrame is missing columns the model requires: {missing}. "
            "This usually means the feature-engineering pipeline used to build "
            "these rows has drifted from the one used at training time."
        )

    X = features[feature_cols]  # explicit selection + ordering, see module docstring
    predictions = artifact["model"].predict(X)
    return pd.Series(predictions, index=features.index, name="predicted_next_week_ppr")
