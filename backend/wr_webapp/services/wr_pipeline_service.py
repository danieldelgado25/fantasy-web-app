"""
wr_pipeline_service.py
=======================

WHY A SEPARATE SERVICE FOR THIS
---------------------------------
This is the ONLY place in the web app that talks to the
`wide-receiver-predictor` pipeline (`build_training_dataset`, which itself
pulls from `nflreadpy` over the network). Every other part of the backend
(routes, projection_service, model_service) goes through this module rather
than importing `wr_predictor` directly.

That indirection is the point of a "service layer": if the upstream pipeline's
function signature changes, or we swap `nflreadpy` for a different data
source, or we need to add retries/logging around the network call — there is
exactly one file to change. Without this layer, a signature change in
`dataset_builder.py` would mean hunting through every route handler that
happened to call it directly.

WHY THE CACHE
---------------
`build_training_dataset` triggers real network I/O (nflreadpy pulling from
nflverse's GitHub-hosted data releases) and non-trivial feature computation.
A weekly-projections page will be requested repeatedly (users flipping
between weeks/teams, auto-refreshing, etc.) for the *same* underlying season
data. Rebuilding the full dataset on every HTTP request would make the API
slow and would hammer the upstream data source for no reason — the past
weeks' stats haven't changed. So we cache the built DataFrame in memory,
keyed by the tuple of seasons requested, with a simple size cap (oldest
entry evicted first) so long-running dev/staging processes don't leak memory.

This is intentionally a simple in-process dict cache, not Redis or a database
— appropriate for a single-process Flask app. If this app grows to multiple
worker processes, this cache would need to move to a shared store; that's
a clearly-scoped future change *because* it's isolated to this one file.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Iterable

import polars as pl

from wr_predictor.dataset_builder import build_training_dataset

from wr_webapp.config import DATASET_CACHE_MAX_ENTRIES

logger = logging.getLogger(__name__)

# season-tuple -> polars.DataFrame. OrderedDict gives us cheap LRU-style
# eviction (move_to_end on access, popitem(last=False) to evict oldest).
_dataset_cache: "OrderedDict[tuple[int, ...], pl.DataFrame]" = OrderedDict()
_cache_lock = threading.Lock()  # Flask's dev server + gunicorn workers can be multi-threaded


def get_weekly_dataset(seasons: Iterable[int]) -> pl.DataFrame:
    """
    Return the WR weekly feature dataset for the given seasons, built via the
    wide-receiver-predictor pipeline (schedule context, lag/rolling features,
    next_week_ppr_points target). Serves from an in-memory cache when possible.

    `merge_ff_opportunity` is left False here — see train_model.py's docstring
    for the schema-mismatch bug in that join. The serving path must build
    features identically to the training path, so this stays in sync with how
    the model was trained.
    """
    key = tuple(sorted(seasons))

    with _cache_lock:
        cached = _dataset_cache.get(key)
        if cached is not None:
            _dataset_cache.move_to_end(key)
            logger.info("wr_pipeline_service: cache hit for seasons=%s", key)
            return cached

    logger.info("wr_pipeline_service: cache miss for seasons=%s, building dataset...", key)
    df = build_training_dataset(
        seasons=list(key),
        min_games_for_player=0,
        merge_ff_opportunity=False,
    )

    with _cache_lock:
        _dataset_cache[key] = df
        _dataset_cache.move_to_end(key)
        while len(_dataset_cache) > DATASET_CACHE_MAX_ENTRIES:
            evicted_key, _ = _dataset_cache.popitem(last=False)
            logger.info("wr_pipeline_service: evicting cached dataset for seasons=%s", evicted_key)

    return df


def clear_cache() -> None:
    """Used by tests, and available as an escape hatch if stale data is ever
    suspected in a long-running process (e.g. after nflverse posts a
    correction to a prior week's box scores)."""
    with _cache_lock:
        _dataset_cache.clear()
