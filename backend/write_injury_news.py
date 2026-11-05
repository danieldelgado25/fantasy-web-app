from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import nflreadpy as nfl
import polars as pl

from wr_predictor import data_loader
from wr_predictor.injury_news import carry_first_seen, current_injury_news

"""
Writes the injury news feed the website's Injuries tab reads. Reads the previous
feed first, so a status keeps the time it was first seen while it doesn't change.
Run from backend/: python write_injury_news.py
"""

# Served as a static file by the frontend, next to the projections.
NEWS_PATH = "../frontend/public/data/injuries.json"


def read_previous_feed(path: str) -> pl.DataFrame | None:
    """The last published feed's entries, or None on the first run."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as feed_file:
        return pl.DataFrame(json.load(feed_file)["players"])


def main() -> None:
    """Build this run's feed from fresh nflverse data and write it."""
    season = nfl.get_current_season()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    current = current_injury_news(data_loader.load_injuries([season]), data_loader.load_weekly_rosters([season]))
    entries = carry_first_seen(current, read_previous_feed(NEWS_PATH), now)

    with open(NEWS_PATH, "w", encoding="utf-8") as feed_file:
        json.dump({"generated_at": now, "players": entries.to_dicts()}, feed_file, indent=1)
    print(f"Wrote {entries.height} injury news entries to {NEWS_PATH}")


if __name__ == "__main__":
    main()
