from __future__ import annotations

"""
Named stat groups, the one place that says which columns the pipeline uses.
Positions are built by combining groups, so a future position reuses what it
shares and adds only what is specific to it. Only WR is defined for now.
"""

# Official PPR points: the main number being projected.
POINTS_STAT = "ppr_points"

# Box-score receiving stats, shared by every skill position.
RECEIVING_STATS = ["targets", "rec", "rec_yds", "rec_td"]

# How much of a team's passing game a player commands.
RECEIVING_USAGE_STATS = ["target_share", "air_yards_share", "wopr", "receiving_air_yards"]

# Rushing stats. Inputs only for rushing projections: in the 2025 backtest, adding
# them to the points model made it worse for WRs who get carries (MAE 4.20 to 4.43).
RUSHING_STATS = ["carries", "rushing_yards"]

# Every stat that gets lag and rolling-average columns.
FEATURE_STATS = [POINTS_STAT, *RECEIVING_STATS, *RECEIVING_USAGE_STATS, *RUSHING_STATS]

# Stats given their own projection, by position.
PREDICTED_STATS_BY_POSITION = {
    "WR": [*RECEIVING_STATS, *RUSHING_STATS, POINTS_STAT],
}

# Position the pipeline currently runs for.
PREDICTED_STATS = PREDICTED_STATS_BY_POSITION["WR"]


def next_week_column(stat: str) -> str:
    """Name of the supervised-learning target column for a stat."""
    return f"next_week_{stat}"
