from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import polars as pl

from wr_predictor.stats import POINTS_STAT, PREDICTED_STATS

"""
The prediction log and how it gets scored. Predictions are saved before kickoff
and compared with actual results afterwards, using only the top players as they
stood when the prediction was made.
"""

# How many top-ranked players are displayed and scored.
TOP_N = 20

# Passing bar: over this many finished weeks, every prediction is made, and the model
# beats the baseline on both average error and ranking. A fixed ranking target doesn't
# work: over 2023-2025 a 4-week average swung from 0.05 to 0.37, so reaching 0.30 was
# largely luck, while the model out-ranked the baseline in 80% of those windows.
GATE_WINDOW_WEEKS = 4

# Stats shown in the weekly predicted-vs-actual review.
REVIEW_STATS = ["targets", "rec", POINTS_STAT]

# Columns that identify a logged prediction.
LOG_KEY = ["season", "week", "player_id"]


def season_points(stats: pl.DataFrame, season: int) -> pl.DataFrame:
    """
    Official regular-season PPR totals per player for `season`, from games already in
    `stats`. Falls back to the previous season before any games have been played.
    Rounded because float sums vary with row order, which would randomly break exact ties.
    """
    regular = stats.filter(pl.col("season_type") == "REG")
    played = regular.filter(pl.col("season") == season)
    if played.is_empty():
        played = regular.filter(pl.col("season") == season - 1)
    return played.group_by("player_id").agg(pl.col("fantasy_points_ppr").sum().round(2).alias("season_points"))


def add_rank(frame: pl.DataFrame, points: pl.DataFrame) -> pl.DataFrame:
    """
    Rank players best-first by season points. Players with none rank last. Sorting
    by player_id first makes tied ranks repeatable, so reruns don't change the output.
    """
    return (
        frame.join(points, on="player_id", how="left")
        .with_columns(pl.col("season_points").fill_null(0.0))
        .sort("player_id")
        .with_columns(pl.col("season_points").rank(method="ordinal", descending=True).cast(pl.Int32).alias("rank"))
    )


def build_log_rows(ranked: pl.DataFrame) -> pl.DataFrame:
    """
    Reduce ranked predictions to the columns worth keeping. Stores each stat's
    baseline, the average of the last 3 games, so it is frozen with the prediction.
    Also stores season points, which decide who is in that week's scored top players.
    """
    return ranked.select(
        *LOG_KEY,
        pl.col("player_display_name").alias("player_name"),
        "team",
        "opponent_team",
        "rank",
        pl.col("season_points").round(2),
        *[pl.col(f"pred_{stat}").round(2) for stat in PREDICTED_STATS],
        *[pl.col(f"{stat}_rolling_3").round(2).alias(f"base_{stat}") for stat in PREDICTED_STATS],
    )


def not_yet_kicked_off(frame: pl.DataFrame, now_eastern: datetime) -> pl.DataFrame:
    """
    Keep rows whose game hasn't started. nflverse schedule times are US Eastern, so
    `now_eastern` must be too. A missing or unreadable time is kept rather than dropped.
    """
    kickoff = (pl.col("gameday") + " " + pl.col("gametime")).str.to_datetime("%Y-%m-%d %H:%M", strict=False)
    return frame.filter(kickoff.is_null() | (kickoff > now_eastern))


def upsert_log(path: str, rows: pl.DataFrame) -> pl.DataFrame:
    """
    Write `rows` into the log at `path`, replacing any earlier prediction for the
    same player and game. Other rows are left alone, so as long as callers only pass
    games that haven't kicked off, a logged prediction can't change after kickoff.
    """
    log_path = Path(path)
    if log_path.exists():
        rows = pl.concat([pl.read_csv(log_path, schema=rows.schema).join(rows, on=LOG_KEY, how="anti"), rows])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows.sort(LOG_KEY)
    rows.write_csv(log_path)
    return rows


def _top_players(log: pl.DataFrame, week: int) -> pl.DataFrame:
    """A week's scored players: those with a game that week, best season points first."""
    return log.filter(pl.col("week") == week).sort(["season_points", "player_id"], descending=[True, False]).head(TOP_N)


def build_review(log: pl.DataFrame, actuals: pl.DataFrame) -> pl.DataFrame:
    """
    One row per top player per week, with predicted and actual values for each reviewed
    stat. A positive difference means the player beat the projection. Players who didn't
    play stay in the table with blank actuals, so a missed game is visible.
    """
    weeks = [_top_players(log, week) for week in sorted(log["week"].unique().to_list())]
    joined = pl.concat(weeks).join(actuals.select(*LOG_KEY, *REVIEW_STATS), on=LOG_KEY, how="left")
    stat_columns = []
    for stat in REVIEW_STATS:
        stat_columns += [
            pl.col(f"pred_{stat}"),
            pl.col(stat).round(2).alias(f"actual_{stat}"),
            (pl.col(stat) - pl.col(f"pred_{stat}")).round(2).alias(f"diff_{stat}"),
        ]
    return joined.select("week", "player_name", "team", "opponent_team", "season_points", *stat_columns)


def score_predictions(log: pl.DataFrame, actuals: pl.DataFrame) -> list[dict]:
    """
    Score each week's top players against actual results, one dict per week.
    `actuals` holds LOG_KEY plus one column per predicted stat. Players with no
    actual result, usually because they didn't play, count as predicted but not scored.
    The top players are picked from those with a game that week using their logged
    season points, so byes can't leave a week short and nothing later affects the pick.
    """
    scores = []
    for week in sorted(log["week"].unique().to_list()):
        cohort = _top_players(log, week)
        played = cohort.join(actuals, on=LOG_KEY, how="inner", suffix="_actual")
        score = {"week": week, "predicted": cohort.height, "played": played.height}
        if played.height >= 2:
            for stat in PREDICTED_STATS:
                score[f"{stat}_mae"] = _mean_abs_error(played, f"pred_{stat}", stat)
                score[f"{stat}_baseline_mae"] = _mean_abs_error(played, f"base_{stat}", stat)
            score["rank_correlation"] = _rank_correlation(played, f"pred_{POINTS_STAT}")
            score["baseline_rank_correlation"] = _rank_correlation(played, f"base_{POINTS_STAT}")
        scores.append(score)
    return scores


def summarize_accuracy(scores: list[dict], gate: dict, completed_weeks: list[int]) -> dict:
    """
    Reduce scores to what the website shows: points accuracy for finished weeks only,
    since an unfinished week's results are incomplete. Undefined values become None,
    because a NaN would make the whole JSON file unreadable in the browser.
    """
    weeks = [
        {
            "week": s["week"],
            "predicted": s["predicted"],
            "played": s["played"],
            "mae": _round_or_none(s[f"{POINTS_STAT}_mae"]),
            "baseline_mae": _round_or_none(s[f"{POINTS_STAT}_baseline_mae"]),
            "rank_correlation": _round_or_none(s["rank_correlation"]),
            "baseline_rank_correlation": _round_or_none(s["baseline_rank_correlation"]),
        }
        for s in scores
        if s["week"] in completed_weeks and "rank_correlation" in s
    ]
    return {"weeks": weeks, "passed": gate["passed"], "reason": gate.get("reason")}


def _round_or_none(value: float | None) -> float | None:
    """Round for display, turning a missing or undefined number into None."""
    return None if value is None or math.isnan(value) else round(value, 2)


def _mean_abs_error(frame: pl.DataFrame, predicted: str, actual: str) -> float:
    """Average absolute difference between two columns."""
    return frame.select((pl.col(predicted) - pl.col(actual)).abs().mean()).item()


def _rank_correlation(frame: pl.DataFrame, predicted: str) -> float:
    """How well a column ordered players by actual points, from -1 to 1."""
    return frame.select(pl.corr(predicted, POINTS_STAT, method="spearman")).item()


def check_gate(scores: list[dict], completed_weeks: list[int]) -> dict:
    """
    Apply the passing bar to the latest finished weeks. Unfinished weeks are ignored
    because their results are incomplete. Returns each check so a failure explains itself.
    """
    finished = [s for s in scores if s["week"] in completed_weeks and "rank_correlation" in s]
    recent = finished[-GATE_WINDOW_WEEKS:]
    if len(recent) < GATE_WINDOW_WEEKS:
        return {"passed": False, "reason": f"needs {GATE_WINDOW_WEEKS} finished weeks, has {len(recent)}"}

    played = sum(s["played"] for s in recent)
    mae = sum(s[f"{POINTS_STAT}_mae"] * s["played"] for s in recent) / played
    baseline_mae = sum(s[f"{POINTS_STAT}_baseline_mae"] * s["played"] for s in recent) / played
    rank_correlation = sum(s["rank_correlation"] for s in recent) / len(recent)
    baseline_rank_correlation = sum(s["baseline_rank_correlation"] for s in recent) / len(recent)

    checks = {
        "all_predictions_made": all(s["predicted"] == TOP_N for s in recent),
        "beats_baseline": mae < baseline_mae,
        "ranks_better_than_baseline": rank_correlation > baseline_rank_correlation,
    }
    return {
        "passed": all(checks.values()),
        "weeks": [s["week"] for s in recent],
        "mae": round(mae, 3),
        "baseline_mae": round(baseline_mae, 3),
        "rank_correlation": round(rank_correlation, 3),
        "baseline_rank_correlation": round(baseline_rank_correlation, 3),
        **checks,
    }
