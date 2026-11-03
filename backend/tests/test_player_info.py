import polars as pl

from wr_predictor.player_info import add_player_info

"""
Uses Pytest to verify the display-only player details added to the website file.
All data is hand-written, so no network is used.
"""


def test_add_player_info_joins_details_and_keeps_players_missing_from_sources() -> None:
    rows = pl.DataFrame({"player_id": ["A", "B"], "team": ["SEA", "XXX"]})
    players = pl.DataFrame(
        {
            "gsis_id": ["A"],
            "headshot": ["https://img/a.png"],
            "jersey_number": ["11"],
            "birth_date": ["2002-02-14"],
            "height": [72],
            "weight": [197],
            "college_name": ["Ohio State"],
            "years_of_experience": [4],
        }
    )
    teams = pl.DataFrame({"team_abbr": ["SEA"], "team_logo_espn": ["https://logo/sea.png"]})
    stats = pl.DataFrame(
        {
            "player_id": ["A", "A", "A"],
            "season": [2026, 2026, 2025],
            "season_type": ["REG", "POST", "REG"],
            "targets": [10, 99, 99],
            "receptions": [7, 99, 99],
            "receiving_yards": [90.0, 99.0, 99.0],
            "receiving_tds": [1, 99, 99],
        }
    )

    result = add_player_info(rows, players, teams, stats, season=2026).sort("player_id")

    # Only 2026 regular-season games count toward the season totals.
    assert result.row(0, named=True) == {
        "player_id": "A",
        "team": "SEA",
        "headshot_url": "https://img/a.png",
        "jersey_number": "11",
        "birth_date": "2002-02-14",
        "height_inches": 72,
        "weight_lbs": 197,
        "college": "Ohio State",
        "years_exp": 4,
        "season_games": 1,
        "season_targets": 10,
        "season_rec": 7,
        "season_rec_yds": 90.0,
        "season_rec_td": 1,
        "team_logo_url": "https://logo/sea.png",
    }
    # A player missing from every source keeps their row, with empty details.
    assert result["headshot_url"][1] is None and result["team_logo_url"][1] is None
