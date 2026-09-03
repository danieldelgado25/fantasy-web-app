from __future__ import annotations

import os
import polars as pl
import nflreadpy as nfl

# Default location for local raw-pull snapshots. Kept independent of nflreadpy's
# own cache: that cache expires and can return corrected data on a later pull,
# so a snapshot here keeps a given dataset build reproducible over time.
RAW_DATA_DIR = "data/raw"


def load_player_weekly_stats(seasons: list[int], raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load weekly player stats from nflreadpy, snapshotting to raw_data_dir.
    """
    return _load_seasons_cached("player_stats", seasons, lambda: nfl.load_player_stats(seasons), raw_data_dir)


def load_players(raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load player metadata, snapshotting to raw_data_dir.
    """
    return _load_cached("players", nfl.load_players, raw_data_dir)


def load_schedules(seasons: list[int], raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load NFL schedules/results, snapshotting to raw_data_dir.
    """
    return _load_seasons_cached("schedules", seasons, lambda: nfl.load_schedules(seasons), raw_data_dir)


def load_injuries(seasons: list[int], raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load injuries/practice participation, snapshotting to raw_data_dir.
    """
    return _load_seasons_cached("injuries", seasons, lambda: nfl.load_injuries(seasons), raw_data_dir)


def load_ff_opportunity(seasons: list[int], raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load fantasy opportunity / expected production data, snapshotting to raw_data_dir.
    Safe fallback if unavailable for your current setup.
    """
    try:
        return _load_seasons_cached("ff_opportunity", seasons, lambda: nfl.load_ff_opportunity(seasons), raw_data_dir)
    except Exception:
        return pl.DataFrame()


def _load_seasons_cached(name: str, seasons: list[int], fetch, raw_data_dir: str) -> pl.DataFrame:
    """
    Read a parquet snapshot for (name, seasons) from raw_data_dir if present,
    otherwise fetch fresh data and write the snapshot before returning it.
    """
    season_tag = "-".join(str(s) for s in sorted(seasons))
    cache_path = os.path.join(raw_data_dir, f"{name}_{season_tag}.parquet")
    return _read_or_fetch(cache_path, fetch, raw_data_dir)


def _load_cached(name: str, fetch, raw_data_dir: str) -> pl.DataFrame:
    """
    Read a parquet snapshot for name (no season scope) from raw_data_dir if
    present, otherwise fetch fresh data and write the snapshot.
    """
    cache_path = os.path.join(raw_data_dir, f"{name}.parquet")
    return _read_or_fetch(cache_path, fetch, raw_data_dir)


def _read_or_fetch(cache_path: str, fetch, raw_data_dir: str) -> pl.DataFrame:
    """
    Shared read-through cache logic used by both cache key styles above.
    """
    if os.path.exists(cache_path):
        return pl.read_parquet(cache_path)
    data_frame = _to_polars(fetch())
    os.makedirs(raw_data_dir, exist_ok=True)
    data_frame.write_parquet(cache_path)
    return data_frame


def _to_polars(data_frame) -> pl.DataFrame:
    """
    nflreadpy is Polars-native, but this keeps the wrapper defensive.
    """
    if isinstance(data_frame, pl.DataFrame):
        return data_frame
    if hasattr(data_frame, "to_pandas"):
        return pl.from_pandas(data_frame.to_pandas())
    return pl.DataFrame(data_frame)
