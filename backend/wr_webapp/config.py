"""
config.py
=========

Shared backend constants: where the trained model artifact lives on disk, and
how large the in-process dataset cache may grow.

WHY THIS IS JUST CONSTANTS NOW
------------------------------
This module used to resolve a filesystem path to a *separate*
`wide-receiver-predictor` checkout and splice it onto `sys.path`, because that
pipeline had no packaging and couldn't be `pip install`ed. It can now: this
repo's `pyproject.toml` packages the pipeline as `wr_predictor`, so
`from wr_predictor... import ...` works after `pip install -e .` with no path
juggling. The old helpers (`resolve_wr_predictor_path`,
`add_wr_predictor_to_path`) and their `WR_PREDICTOR_PATH` / sibling-directory
lookup were removed once `train_model.py` and `wr_pipeline_service.py` switched
to the packaged import and nothing else referenced them.
"""

from __future__ import annotations

from pathlib import Path

# backend/wr_webapp/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Where the training script writes, and the model service reads, the serialized
# model artifact. Defined here so both sides agree on the location.
ARTIFACT_PATH = BACKEND_ROOT / "artifacts" / "wr_model_v1.joblib"

# Max number of built feature datasets held in the in-memory cache at once,
# keyed by season tuple. See services/wr_pipeline_service.py for the rationale.
DATASET_CACHE_MAX_ENTRIES = 8
