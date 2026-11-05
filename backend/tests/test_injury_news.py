import polars as pl

from wr_predictor.injury_news import RESERVE_NOTE, carry_first_seen, current_injury_news

"""
Uses Pytest to verify the injury news feed. All data is hand-written, so no network is used.
"""

DNP = "Did Not Participate In Practice"


def test_current_injury_news_uses_latest_week_and_reserve_beats_report() -> None:
    injuries = pl.DataFrame(
        {
            "gsis_id": ["A", "B", "C", "D", "OLD"],
            "full_name": ["Ann", "Bo", "Cy", "Di", "Old"],
            "team": ["SEA"] * 5,
            "position": ["WR", "WR", "WR", "TE", "WR"],
            # OLD is only on last week's report, so it must not appear.
            "season": [2026] * 5,
            "week": [9, 9, 9, 9, 8],
            "report_status": ["Questionable", None, "Out", "Out", "Out"],
            "practice_status": [DNP, "Full Participation in Practice", DNP, DNP, DNP],
            "report_primary_injury": ["Ankle", None, "Knee", "Knee", "Knee"],
            "practice_primary_injury": ["Ankle", None, "Knee", "Knee", "Knee"],
        }
    )
    # C is also on a reserve list, which should win over the report's Out.
    rosters = pl.DataFrame(
        {
            "gsis_id": ["C", "E", "F"],
            "full_name": ["Cy", "Ed", "Fa"],
            "team": ["SEA", "DAL", "DAL"],
            "position": ["WR", "WR", "WR"],
            "week": [9, 9, 9],
            "status": ["RES", "RES", "ACT"],
        }
    )

    result = current_injury_news(injuries, rosters).sort("player_id")

    # B is healthy, D is a TE, OLD is stale, F is active: none appear.
    assert dict(zip(result["player_id"], result["injury_status"])) == {"A": "DNP", "C": "IR", "E": "IR"}
    assert result.filter(pl.col("player_id") == "C")["injury_note"].item() == RESERVE_NOTE


def test_carry_first_seen_keeps_time_for_unchanged_status_and_sorts_newest_first() -> None:
    previous = pl.DataFrame(
        {
            "player_id": ["A", "B"],
            "injury_status": ["Questionable", "DNP"],
            "first_seen": ["2026-11-04T08:20:00+00:00", "2026-11-04T08:20:00+00:00"],
        }
    )
    # A is unchanged, B got worse, C is new.
    current = pl.DataFrame(
        {
            "player_id": ["A", "B", "C"],
            "injury_status": ["Questionable", "Out", "Doubtful"],
            "injury_note": ["q", "o", "d"],
        }
    )
    now = "2026-11-05T08:20:00+00:00"

    result = carry_first_seen(current, previous, now)

    # B and C are new now, the worse one first; A keeps its original time.
    assert result["player_id"].to_list() == ["B", "C", "A"]
    assert result["first_seen"].to_list() == [now, now, "2026-11-04T08:20:00+00:00"]


def test_carry_first_seen_without_a_previous_feed_marks_everything_now() -> None:
    current = pl.DataFrame({"player_id": ["A"], "injury_status": ["Out"], "injury_note": ["o"]})
    assert carry_first_seen(current, None, "T")["first_seen"].to_list() == ["T"]
