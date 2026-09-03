import polars as pl
import pytest
from sklearn.pipeline import Pipeline

from wr_predictor import model


"""
Uses Pytest to verify wr_predictor.model: feature-column selection, the two
null-drop strategies in prepare_model_frame, the 3-way season split (and its
overlap guard), the model pipeline factory, the shared metrics helper, the
baseline scorer, and Ridge alpha selection on validation RMSE.

Synthetic polars DataFrames only -- no dataset build, no network.
"""


def _frame() -> pl.DataFrame:
    """A small model-ready frame: two feature columns (one `_rolling_3`, one
    not), the target, the baseline column, and one meta column."""
    return pl.DataFrame(
        {
            "player_id": ["A", "A", "A", "A"],
            "season": [2021, 2022, 2023, 2024],
            "temp": [70.0, None, 60.0, 55.0],          # non-rolling feature, has a null
            "x_rolling_3": [1.0, 2.0, 3.0, 4.0],       # rolling-3 feature
            "ppr_points_rolling_3": [5.0, 6.0, 7.0, 8.0],
            "next_week_ppr_points": [12.0, 14.0, 16.0, 18.0],
        }
    )


def test_get_feature_columns_excludes_meta_target_and_non_numeric() -> None:
    frame = _frame().with_columns(pl.lit("REG").alias("season_type"))  # meta, non-numeric
    features = model.get_feature_columns(frame)

    assert set(features) == {"temp", "x_rolling_3", "ppr_points_rolling_3"}
    assert "season" not in features            # meta
    assert "next_week_ppr_points" not in features  # target
    assert "season_type" not in features       # meta + non-numeric


def test_prepare_model_frame_rolling_3_keeps_rows_with_other_nulls() -> None:
    """Default require='rolling_3': a null `temp` (dome game) must NOT drop the
    row; only null rolling-3 features or a null target do."""
    frame = _frame()
    features = model.get_feature_columns(frame)

    kept = model.prepare_model_frame(frame, features)  # default require

    assert kept.height == 4  # the null-temp row survives


def test_prepare_model_frame_rolling_3_drops_null_rolling_and_null_target() -> None:
    frame = _frame().with_columns(
        pl.Series("x_rolling_3", [None, 2.0, 3.0, 4.0]),
        pl.Series("next_week_ppr_points", [12.0, None, 16.0, 18.0]),
    )
    features = model.get_feature_columns(frame)

    kept = model.prepare_model_frame(frame, features)

    assert kept.height == 2  # rows 0 (null rolling) and 1 (null target) gone


def test_prepare_model_frame_all_drops_any_null_feature() -> None:
    frame = _frame()
    features = model.get_feature_columns(frame)

    kept = model.prepare_model_frame(frame, features, require="all")

    assert kept.height == 3  # the null-temp row is dropped under 'all'


def test_prepare_model_frame_rejects_unknown_require() -> None:
    with pytest.raises(ValueError):
        model.prepare_model_frame(_frame(), ["x_rolling_3"], require="sometimes")


def test_split_train_val_test_partitions_by_season() -> None:
    train, val, test = model.split_train_val_test(
        _frame(), train_seasons=[2021, 2022], validation_seasons=[2023], test_seasons=[2024]
    )

    assert train["season"].to_list() == [2021, 2022]
    assert val["season"].to_list() == [2023]
    assert test["season"].to_list() == [2024]


def test_split_train_val_test_rejects_overlapping_seasons() -> None:
    with pytest.raises(ValueError):
        model.split_train_val_test(_frame(), [2021, 2022], [2022], [2024])


def test_build_model_pipeline_wires_alpha_into_ridge() -> None:
    pipeline = model.build_model_pipeline(alpha=7.0)

    assert isinstance(pipeline, Pipeline)
    assert [name for name, _ in pipeline.steps] == ["impute", "scaler", "ridge"]
    assert pipeline.named_steps["ridge"].alpha == 7.0


def test_regression_metrics_on_perfect_prediction() -> None:
    y = [1.0, 2.0, 3.0, 4.0]
    metrics = model.regression_metrics(y, y)

    assert metrics == {"mae": 0.0, "rmse": 0.0, "r2": 1.0, "n": 4}


def test_evaluate_baseline_scores_rolling_3_against_target() -> None:
    metrics = model.evaluate_baseline(_frame())

    # baseline (5,6,7,8) vs target (12,14,16,18): constant error of 7,8,9,10
    assert metrics["n"] == 4
    assert metrics["mae"] == pytest.approx(8.5)


def test_select_best_ridge_picks_lowest_validation_rmse() -> None:
    frame = _frame()
    features = model.get_feature_columns(frame)
    train, val, _ = model.split_train_val_test(frame, [2021, 2022], [2023], [2024])

    best = model.select_best_ridge(train, val, features, alpha_grid=[0.1, 1.0, 1000.0])

    assert set(best) == {"alpha", "model", "val_rmse"}
    assert best["alpha"] in {0.1, 1.0, 1000.0}
    # every alpha in the grid must have been at least as bad on the val set
    per_alpha = {
        a: model._rmse(
            val["next_week_ppr_points"].to_numpy(),
            model.build_model_pipeline(a)
            .fit(
                model.feature_matrix(train, features),
                train["next_week_ppr_points"].to_numpy(),
            )
            .predict(model.feature_matrix(val, features)),
        )
        for a in (0.1, 1.0, 1000.0)
    }
    assert best["val_rmse"] == pytest.approx(min(per_alpha.values()))


def test_select_best_ridge_rejects_empty_grid() -> None:
    frame = _frame()
    features = model.get_feature_columns(frame)
    train, val, _ = model.split_train_val_test(frame, [2021, 2022], [2023], [2024])

    with pytest.raises(ValueError):
        model.select_best_ridge(train, val, features, alpha_grid=[])
