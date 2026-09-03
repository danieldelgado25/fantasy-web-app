import polars as pl
import pytest

from src.wr_predictor.targets import add_next_week_target, drop_rows_without_target


"""
Uses Pytest to verify add_next_week_target and drop_rows_without_target behave as expected.
"""


def test_add_next_week_target_shifts_within_player() -> None:
    data_frame = pl.DataFrame(
        {
            "player_id": ["A", "A", "A", "B", "B"],
            "season": [2024, 2024, 2024, 2024, 2024],
            "week": [1, 2, 3, 1, 2],
            "ppr_points": [10.0, 20.0, 30.0, 5.0, 15.0],
        }
    )

    result = add_next_week_target(data_frame).sort(["player_id", "week"])

    # Each player's next_week_ppr_points is the following week's own points;
    # the shift must not cross from player B's points into player A's last row.
    assert result["next_week_ppr_points"].to_list() == [20.0, 30.0, None, 15.0, None]


def test_add_next_week_target_sorts_unordered_input() -> None:
    data_frame = pl.DataFrame(
        {
            "player_id": ["A", "A"],
            "season": [2024, 2024],
            "week": [2, 1],
            "ppr_points": [20.0, 10.0],
        }
    )

    result = add_next_week_target(data_frame).sort("week")

    assert result["next_week_ppr_points"].to_list() == [20.0, None]


def test_add_next_week_target_missing_id_columns_raises() -> None:
    data_frame = pl.DataFrame({"ppr_points": [10.0]})

    with pytest.raises(ValueError):
        add_next_week_target(data_frame)


def test_add_next_week_target_missing_ppr_points_raises() -> None:
    data_frame = pl.DataFrame(
        {
            "player_id": ["A"],
            "season": [2024],
            "week": [1],
        }
    )

    with pytest.raises(ValueError):
        add_next_week_target(data_frame)


def test_drop_rows_without_target_removes_nulls() -> None:
    data_frame = pl.DataFrame({"next_week_ppr_points": [10.0, None, 5.0]})

    result = drop_rows_without_target(data_frame)

    assert result["next_week_ppr_points"].to_list() == [10.0, 5.0]
