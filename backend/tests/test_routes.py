import polars as pl
import pytest

from api import routes
from api.app import create_app

"""
Uses Pytest + Flask's test client to verify /api/players and /api/projections.
The model/snapshot artifacts are monkeypatched directly onto the routes
module's cache, so no real training run or file I/O is needed.
"""


@pytest.fixture()
def client():
    return create_app().test_client()


@pytest.fixture(autouse=True)
def reset_artifact_cache(monkeypatch):
    # _load_artifacts caches into module globals on first call; reset them
    # between tests so one test's monkeypatching can't leak into another.
    monkeypatch.setattr(routes, "_model", None)
    monkeypatch.setattr(routes, "_feature_columns", None)
    monkeypatch.setattr(routes, "_snapshot", None)


class _FakePath:
    """Stand-in for MODEL_PATH/SNAPSHOT_PATH: pathlib.Path can't have its
    exists() monkeypatched per-instance (it's a slotted class), so routes.py's
    module-level path constants are swapped for this instead."""

    def __init__(self, exists_value: bool):
        self._exists_value = exists_value

    def exists(self) -> bool:
        return self._exists_value

    def __str__(self) -> str:
        return "/fake/path"


def test_projections_returns_501_when_artifacts_missing(client, monkeypatch):
    monkeypatch.setattr(routes, "MODEL_PATH", _FakePath(False))
    monkeypatch.setattr(routes, "SNAPSHOT_PATH", _FakePath(False))

    response = client.get("/api/projections?player_id=X")

    assert response.status_code == 501


def _fake_model():
    class FakeModel:
        def predict(self, x):
            return [12.34]

    return FakeModel()


def _patch_loaded_artifacts(monkeypatch):
    snapshot = pl.DataFrame(
        {
            "player_id": ["00-1"],
            "player_display_name": ["Test Player"],
            "team": ["SEA"],
            "opponent_team": ["NE"],
            "season": [2026],
            "week": [1],
            "some_feature": [1.0],
        }
    )
    monkeypatch.setattr(routes, "MODEL_PATH", _FakePath(True))
    monkeypatch.setattr(routes, "SNAPSHOT_PATH", _FakePath(True))
    monkeypatch.setattr(routes, "load_model", lambda path: (_fake_model(), ["some_feature"]))
    monkeypatch.setattr(routes.pl, "read_parquet", lambda path: snapshot)


def test_players_lists_snapshot_rows(client, monkeypatch):
    _patch_loaded_artifacts(monkeypatch)

    response = client.get("/api/players")

    assert response.status_code == 200
    assert response.get_json() == [{"player_id": "00-1", "player_name": "Test Player", "team": "SEA"}]


def test_projections_requires_player_id(client, monkeypatch):
    _patch_loaded_artifacts(monkeypatch)

    response = client.get("/api/projections")

    assert response.status_code == 400


def test_projections_returns_404_for_unknown_player(client, monkeypatch):
    _patch_loaded_artifacts(monkeypatch)

    response = client.get("/api/projections?player_id=nonexistent")

    assert response.status_code == 404


def test_projections_returns_prediction_for_known_player(client, monkeypatch):
    _patch_loaded_artifacts(monkeypatch)

    response = client.get("/api/projections?player_id=00-1")

    assert response.status_code == 200
    body = response.get_json()
    assert body["player_name"] == "Test Player"
    assert body["opponent_team"] == "NE"
    assert body["season"] == 2026
    assert body["week"] == 1
    assert body["projected_ppr_points"] == 12.34
    assert body["model_version"] == "ridge-v1"
