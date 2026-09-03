import sys

from wr_predictor.dataset_builder import build_training_dataset
from wr_predictor.model import (
    TARGET_COLUMN,
    evaluate_baseline,
    feature_matrix,
    get_feature_columns,
    prepare_model_frame,
    regression_metrics,
    select_best_ridge,
    split_train_val_test,
)


def main() -> None:
    """
    Script to build the training dataset.
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    training_data_frame = build_training_dataset(
        seasons=[2021, 2022, 2023, 2024],
        min_games_for_player=0,
        output_path="data/processed/wr_training_dataset_2021-2024.csv",
    )

    """
    Evaluation / Prediction data 2025 season
    Same filters as training data, but only 2025 season
    """
    evaluation_2025_data_frame = build_training_dataset(
        seasons=[2025],
        min_games_for_player=0,
        output_path="data/processed/wr_evaluation_dataset_2025.csv",
    )

    print(training_data_frame.head())
    print(f"\nRows: {training_data_frame.shape[0]}")
    print(f"Cols: {training_data_frame.shape[1]}")

    print(evaluation_2025_data_frame.head())
    print(f"\nRows: {evaluation_2025_data_frame.shape[0]}")
    print(f"Cols: {evaluation_2025_data_frame.shape[1]}")

    """
    Season-holdout model evaluation: train on 2021-2022, validate on 2023,
    test on 2024. Uses the same wr_predictor.model helpers as
    backend/training/train_model.py, so this quick check and the shipped
    artifact stay comparable.
    """
    feature_columns = get_feature_columns(training_data_frame)
    model_frame = prepare_model_frame(training_data_frame, feature_columns)
    train_split, validation_split, test_split = split_train_val_test(
        model_frame,
        train_seasons=[2021, 2022],
        validation_seasons=[2023],
        test_seasons=[2024],
    )

    best = select_best_ridge(train_split, validation_split, feature_columns)
    baseline_metrics = evaluate_baseline(test_split)
    ridge_metrics = regression_metrics(
        test_split[TARGET_COLUMN].to_numpy(),
        best["model"].predict(feature_matrix(test_split, feature_columns)),
    )

    print(f"\nChosen Ridge alpha: {best['alpha']}")
    print(f"Baseline (rolling-3 avg) test: MAE={baseline_metrics['mae']:.3f} RMSE={baseline_metrics['rmse']:.3f} R2={baseline_metrics['r2']:.3f}")
    print(f"Ridge regression         test: MAE={ridge_metrics['mae']:.3f} RMSE={ridge_metrics['rmse']:.3f} R2={ridge_metrics['r2']:.3f}")


if __name__ == "__main__":
    main()