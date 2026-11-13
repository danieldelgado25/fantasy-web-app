from __future__ import annotations

import json
import os

import polars as pl

"""
Flattens the site's published data into CSVs for a Power BI accuracy dashboard.
Run from backend/ after evaluate.py: python export_powerbi.py
Reads only files already in frontend/public/data, so it needs no network.
"""

# Published files the export reads.
DATA_DIR = "../frontend/public/data"

# Where the CSVs go. Gitignored, since they can be regenerated at any time.
EXPORT_DIR = "exports"


def load(name: str) -> dict:
    """Read one published JSON file from DATA_DIR."""
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    """Write player_weeks.csv, player_reliability.csv and weekly_accuracy.csv."""
    history = load("player_history.json")
    accuracy = load("accuracy.json")

    # Names and teams, so the dashboard shows players rather than ids.
    names = pl.DataFrame(load("projections.json")["players"]).select("player_id", "player_name", "team")

    # One row per player per finished week; abs_error is what MAE averages.
    weeks = pl.DataFrame(
        [{"player_id": pid, **week} for pid, rows in history["players"].items() for week in rows],
        infer_schema_length=None,
    ).with_columns((pl.col("actual") - pl.col("projected")).abs().round(2).alias("abs_error"))

    # One row per player: grade, games and dud/boom rates for this season.
    # A blank grade means under 4 games; spelled out so it's a real category in Power BI.
    reliability = pl.DataFrame(
        [{"player_id": pid, **row} for pid, row in history["reliability"].items()], infer_schema_length=None
    ).with_columns(pl.col("grade").fill_null("Not graded"))

    # One row per scored week of each week's top players, live and replay kept apart by `source`.
    weekly = pl.DataFrame(
        [{"source": source, **week} for source in ("live", "replay") for week in accuracy.get(source, {}).get("weeks", [])],
        infer_schema_length=None,
    )

    os.makedirs(EXPORT_DIR, exist_ok=True)
    names.join(weeks, on="player_id").sort("player_name", "week").write_csv(os.path.join(EXPORT_DIR, "player_weeks.csv"))
    names.join(reliability, on="player_id").sort("player_name").write_csv(os.path.join(EXPORT_DIR, "player_reliability.csv"))
    weekly.write_csv(os.path.join(EXPORT_DIR, "weekly_accuracy.csv"))
    print(f"Wrote {weeks.height} player-weeks, {reliability.height} players and {weekly.height} scored weeks to {EXPORT_DIR}/")


if __name__ == "__main__":
    main()
