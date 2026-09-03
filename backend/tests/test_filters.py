import polars as pl

from src.wr_predictor.filters import (
    drop_special_teams_only_rows,
    filter_wide_receivers,
    select_wr_columns,
)


"""
Uses Pytest to verify filter_wide_receivers, drop_special_teams_only_rows,
and select_wr_columns behave as expected.
"""


def test_filter_wide_receivers_keeps_only_wr() -> None:
    data_frame = pl.DataFrame({"position": ["WR", "RB", "WR", "QB"]})

    result = filter_wide_receivers(data_frame)

    assert result["position"].to_list() == ["WR", "WR"]


def test_drop_special_teams_only_rows_keeps_offensive_rows() -> None:
    # Row has both offense (targets) and return activity; offense keeps it regardless.
    data_frame = pl.DataFrame(
        {
            "targets": [3],
            "kickoff_return_yards": [25],
        }
    )

    result = drop_special_teams_only_rows(data_frame)

    assert result.height == 1


def test_drop_special_teams_only_rows_drops_return_only_rows() -> None:
    # No offensive usage, but has return-game stats: this is the row we want removed.
    data_frame = pl.DataFrame(
        {
            "targets": [0],
            "kickoff_return_yards": [25],
        }
    )

    result = drop_special_teams_only_rows(data_frame)

    assert result.height == 0


def test_drop_special_teams_only_rows_keeps_zero_activity_rows() -> None:
    # No offense and no return stats either: not a "special-teams-only" row, so it stays.
    data_frame = pl.DataFrame(
        {
            "targets": [0],
            "kickoff_return_yards": [0],
        }
    )

    result = drop_special_teams_only_rows(data_frame)

    assert result.height == 1


def test_drop_special_teams_only_rows_passthrough_without_relevant_columns() -> None:
    # Neither offensive nor special-teams columns present: nothing to filter on.
    data_frame = pl.DataFrame({"unrelated_col": [1, 2]})

    result = drop_special_teams_only_rows(data_frame)

    assert result.height == 2


def test_select_wr_columns_drops_unlisted_and_missing_columns() -> None:
    data_frame = pl.DataFrame(
        {
            "player_id": ["A"],
            "targets": [5],
            "passing_yards": [300],  # QB stat, not in keep_columns
        }
    )

    result = select_wr_columns(data_frame)

    assert set(result.columns) == {"player_id", "targets"}
