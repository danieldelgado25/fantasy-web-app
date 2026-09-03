"""
config.py
=========

WHY THIS FILE EXISTS
---------------------
This app is a *consumer* of the `wide-receiver-predictor` repo — it imports
that repo's `src.wr_predictor` package to build feature rows the same way the
training pipeline does. But that repo isn't published as an installable pip
package (no `pyproject.toml`/`setup.py`), so we can't just `pip install` it.

Instead, we resolve a filesystem path to a local checkout of that repo and add
it to `sys.path` at runtime. Centralizing that path-resolution logic here (one
function, `add_wr_predictor_to_path`) means every entry point that needs the
pipeline — the training script, the Flask app, tests — resolves the path the
same way instead of each guessing independently.

HOW THE PATH IS RESOLVED
--------------------------
1. `WR_PREDICTOR_PATH` env var, if set — explicit override, always wins.
2. A sibling directory named `wide-receiver-predictor` next to this repo's
   root (i.e. `../wide-receiver-predictor` relative to `fantasy-wr-webapp/`).
   This matches how you'd have both repos checked out side by side locally.
3. Otherwise, raise a clear error rather than failing with a confusing
   `ModuleNotFoundError: No module named 'src'` deep inside dataset_builder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# backend/wr_webapp/config.py -> backend/ -> fantasy-wr-webapp/ (repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SIBLING_PATH = REPO_ROOT.parent / "wide-receiver-predictor"

# Where the training script writes, and the model service reads, the
# serialized model artifact. Kept here so both sides agree on the location.
ARTIFACT_PATH = BACKEND_ROOT / "artifacts" / "wr_model_v1.joblib"

# In-memory cache of built feature datasets, keyed by a tuple of seasons.
# See services/wr_pipeline_service.py for why this cache exists.
DATASET_CACHE_MAX_ENTRIES = 8


def resolve_wr_predictor_path() -> Path:
    """Return the filesystem path to the wide-receiver-predictor checkout."""
    env_path = os.environ.get("WR_PREDICTOR_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        path = DEFAULT_SIBLING_PATH.resolve()

    if not (path / "src" / "wr_predictor").is_dir():
        raise RuntimeError(
            "Could not find the wide-receiver-predictor source at "
            f"'{path}'. Clone https://github.com/danieldelgado25/"
            "wide-receiver-predictor next to this repo, or set the "
            "WR_PREDICTOR_PATH environment variable to point at your "
            "checkout."
        )
    return path


def add_wr_predictor_to_path() -> Path:
    """
    Insert the wide-receiver-predictor repo root onto sys.path (idempotent),
    so `from src.wr_predictor import ...` works exactly like it does inside
    that repo's own notebooks. Returns the resolved path for logging/tests.
    """
    path = resolve_wr_predictor_path()
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    return path
