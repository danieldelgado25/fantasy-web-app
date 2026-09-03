"""
projection_service.py
======================

WHY THIS SITS BETWEEN THE OTHER TWO SERVICES
-----------------------------------------------
`wr_pipeline_service` knows how to build historical feature rows.
`model_service` knows how to turn a row of features into a number.
Neither of them knows anything about "a week's worth of projections for the
dashboard" — that's a web-app-specific concept, not part of the underlying ML
pipeline. This module is where that concept lives: it's the orchestration /
business-logic layer that routes.py calls, so route handlers stay thin
(parse the request, call this, format the response) instead of mixing HTTP
concerns with feature engineering.

THE CORE IDEA: "AS OF" ROWS
------------------------------
The model predicts *next week's* PPR points from features known *before* that
week is played. So to project week W of season S for a given player, we need
that player's most recent completed game strictly before (S, W) — its
rolling averages, prior-week stats, etc. — and run the model on THAT row.
This mirrors exactly what notebooks/02_ML_exploration.ipynb does in its
"Projections for a target week" section (`projection_rows`): take the last
regular-season row before the target week, per player, and predict from it.

We reuse that same logic here rather than inventing a different one, so a
projection produced by this API matches what you'd get running the notebook
by hand for the same week.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from wr_webapp.services import model_service, wr_pipeline_service

# How many prior seasons of data to pull in alongside the target season.
# Early-season weeks (e.g. week 1-3) need a prior season's tail games to have
# any rolling-average history at all; this window keeps that available
# without pulling a player's entire career every time.
LOOKBACK_SEASONS = 2

DISPLAY_COLUMNS = [
    "player_id",
    "player_display_name",
    "player_name",
    "team",
    "opponent_team",
    "season",
    "week",
]


@dataclass
class ProjectionFilters:
    """Typed container for the filters a route can apply. Keeping this as a
    small dataclass (rather than passing team/season/week as loose positional
    args) makes it obvious at every call site what's optional vs required,
    and gives IDEs/tests something concrete to check against."""

    target_season: int
    target_week: int
    team: str | None = None
    limit: int | None = None


def get_weekly_projections(filters: ProjectionFilters) -> list[dict]:
    """
    Return next-week PPR point projections for every WR with enough recent
    history, as of `filters.target_season`/`filters.target_week`, optionally
    filtered to one team and/or capped to `limit` rows (sorted by projection
    descending — best plays first, matching how a fantasy dashboard is used).
    """
    seasons = list(range(filters.target_season - LOOKBACK_SEASONS, filters.target_season + 1))
    weekly = wr_pipeline_service.get_weekly_dataset(seasons)

    as_of_rows = _select_as_of_rows(weekly, filters.target_season, filters.target_week)
    if as_of_rows.is_empty():
        return []

    if filters.team:
        as_of_rows = as_of_rows.filter(pl.col("team") == filters.team.upper())
        if as_of_rows.is_empty():
            return []

    pdf = as_of_rows.to_pandas()
    predictions = model_service.predict(pdf)
    pdf = pdf.assign(predicted_next_week_ppr=predictions.round(2))

    pdf = pdf.sort_values("predicted_next_week_ppr", ascending=False)
    if filters.limit:
        pdf = pdf.head(filters.limit)

    keep_cols = [c for c in DISPLAY_COLUMNS if c in pdf.columns] + ["predicted_next_week_ppr"]
    return pdf[keep_cols].to_dict(orient="records")


def _select_as_of_rows(weekly: pl.DataFrame, target_season: int, target_week: int) -> pl.DataFrame:
    """
    For each player, take their most recent regular-season row strictly
    before (target_season, target_week), and require the rolling-3 feature
    columns to be non-null (matches the training-time null-drop, so we never
    hand the model a row shaped differently than what it was trained on).
    """
    prior = weekly.filter(
        (pl.col("season") < target_season)
        | ((pl.col("season") == target_season) & (pl.col("week") < target_week))
    )
    if "season_type" in prior.columns:
        prior = prior.filter(pl.col("season_type") == "REG")

    prior = prior.sort(["player_id", "season", "week"])
    as_of = prior.unique(subset=["player_id"], keep="last")

    roll3_cols = [c for c in as_of.columns if c.endswith("_rolling_3")]
    if roll3_cols:
        mask = pl.col(roll3_cols[0]).is_not_null()
        for col in roll3_cols[1:]:
            mask = mask & pl.col(col).is_not_null()
        as_of = as_of.filter(mask)

    return as_of


def get_available_teams(target_season: int) -> list[str]:
    """Distinct team codes present in the target season's data — powers the
    frontend's team filter dropdown without hardcoding a team list that would
    go stale on relocations/rebrands."""
    weekly = wr_pipeline_service.get_weekly_dataset([target_season])
    if weekly.is_empty() or "team" not in weekly.columns:
        return []
    teams = weekly.select(pl.col("team")).unique().to_series().to_list()
    return sorted(t for t in teams if t)
