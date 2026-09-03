import polars as pl

from src.wr_predictor.data_loader import (
    _load_cached,
    _load_seasons_cached,
    _read_or_fetch,
    _to_polars,
)


"""
Uses Pytest to verify the local parquet snapshot caching layer in data_loader.py.
Exercises the private helpers directly with a fake fetch function so no real
nflreadpy/network call is made.
"""


def test_read_or_fetch_writes_snapshot_on_cache_miss(tmp_path) -> None:
    raw_data_dir = str(tmp_path)
    cache_path = f"{raw_data_dir}/sample.parquet"
    fetch_calls = []

    def fetch() -> pl.DataFrame:
        fetch_calls.append(1)
        return pl.DataFrame({"a": [1, 2]})

    result = _read_or_fetch(cache_path, fetch, raw_data_dir)

    assert len(fetch_calls) == 1
    assert result["a"].to_list() == [1, 2]
    assert (tmp_path / "sample.parquet").exists()


def test_read_or_fetch_uses_cache_on_hit_without_calling_fetch(tmp_path) -> None:
    raw_data_dir = str(tmp_path)
    cache_path = f"{raw_data_dir}/sample.parquet"
    # Pre-seed the cache directly so a hit is distinguishable from a fresh fetch.
    pl.DataFrame({"a": [99]}).write_parquet(cache_path)

    def fetch() -> pl.DataFrame:
        raise AssertionError("fetch should not be called on a cache hit")

    result = _read_or_fetch(cache_path, fetch, raw_data_dir)

    assert result["a"].to_list() == [99]


def test_load_seasons_cached_builds_sorted_season_tag_filename(tmp_path) -> None:
    raw_data_dir = str(tmp_path)

    _load_seasons_cached("stats", [2023, 2021], lambda: pl.DataFrame({"a": [1]}), raw_data_dir)

    assert (tmp_path / "stats_2021-2023.parquet").exists()


def test_load_cached_builds_name_only_filename(tmp_path) -> None:
    raw_data_dir = str(tmp_path)

    _load_cached("players", lambda: pl.DataFrame({"a": [1]}), raw_data_dir)

    assert (tmp_path / "players.parquet").exists()


def test_to_polars_passes_through_existing_dataframe() -> None:
    data_frame = pl.DataFrame({"a": [1]})

    assert _to_polars(data_frame) is data_frame


def test_to_polars_converts_plain_dict_fallback() -> None:
    # No to_pandas attribute and not already a DataFrame: falls through to
    # the final pl.DataFrame(data_frame) branch.
    result = _to_polars({"a": [1, 2]})

    assert isinstance(result, pl.DataFrame)
    assert result["a"].to_list() == [1, 2]
