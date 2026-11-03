from __future__ import annotations

import io
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl

from wr_predictor import data_loader
from wr_predictor.dataset_builder import team_game_context
from wr_predictor.predictions import changed_after_kickoff

"""
Enforces the prediction log's freeze: fails if any commit added, edited or removed a
logged prediction for a game that had already kicked off when the commit was made.
Checks every commit that touched a season log, so the whole history is verified on
each run, not just the latest change.
Run from backend/: python check_freeze.py
"""

# Season logs only. Replays (e.g. 2026_replay.csv) are regenerated later by design.
SEASON_LOG = re.compile(r"^backend/predictions/(\d{4})\.csv$")

# Empty log with no columns, for a file that didn't exist before a commit.
EMPTY = pl.DataFrame()


def _git(*args: str) -> str:
    """Run a git command from the repository and return its output."""
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _log_at(commit: str, path: str) -> pl.DataFrame:
    """The log file as it was at `commit`, or empty if it didn't exist yet."""
    try:
        return pl.read_csv(io.StringIO(_git("show", f"{commit}:{path}")), infer_schema_length=0)
    except subprocess.CalledProcessError:
        return EMPTY


def main() -> None:
    """Check each log-changing commit, oldest first, and exit non-zero on any violation."""
    # ponytail: trusts git's author time, which a committer can set. GitHub's push
    # time would be stronger, but needs the API; the public history is the backstop.
    commits = _git("rev-list", "--reverse", "--no-merges", "--format=%H %at", "HEAD", "--", "predictions/").split("\n")
    pairs = [line.split() for line in commits if line and not line.startswith("commit ")]
    schedules: dict[int, pl.DataFrame] = {}
    failures = 0

    for commit, timestamp in pairs:
        at_eastern = datetime.fromtimestamp(int(timestamp), ZoneInfo("America/New_York")).replace(tzinfo=None)
        for path in _git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).split():
            match = SEASON_LOG.match(path)
            if not match:
                continue
            season = int(match.group(1))
            if season not in schedules:
                schedules[season] = team_game_context(data_loader.load_schedules([season]))
            old, new = _log_at(f"{commit}^", path), _log_at(commit, path)
            if new.is_empty():
                new = old.clear()
            if old.is_empty():
                old = new.clear()
            # Logs are read as text, so the schedule's keys are cast to match.
            schedule = schedules[season].with_columns(pl.col("season", "week").cast(pl.Utf8))
            bad = changed_after_kickoff(old, new, schedule, at_eastern)
            if not bad.is_empty():
                failures += bad.height
                print(f"{commit[:7]} changed {bad.height} predictions after kickoff in {path}:\n{bad}")

    print(f"Checked {len(pairs)} commits that touched the prediction logs.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
