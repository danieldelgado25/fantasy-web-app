import sys

from src.wr_predictor.dataset_builder import build_training_dataset
from src.wr_predictor.model import (
    evaluate_baseline,
    get_feature_columns,
    prepare_model_frame,
    split_by_season,
    train_and_evaluate_ridge,
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
    Season-holdout model evaluation: train on 2021-2023, validate on 2024.
    Compares a naive rolling-average baseline against a first Ridge model.
    """
    feature_columns = get_feature_columns(training_data_frame)
    model_frame = prepare_model_frame(training_data_frame, feature_columns)
    train_split, validation_split = split_by_season(
        model_frame, train_seasons=[2021, 2022, 2023], validation_seasons=[2024]
    )

    baseline_metrics = evaluate_baseline(validation_split)
    ridge_metrics = train_and_evaluate_ridge(train_split, validation_split, feature_columns)

    print(f"\nBaseline (rolling-3 avg): MAE={baseline_metrics['mae']:.3f} RMSE={baseline_metrics['rmse']:.3f}")
    print(f"Ridge regression:         MAE={ridge_metrics['mae']:.3f} RMSE={ridge_metrics['rmse']:.3f}")


if __name__ == "__main__":
    main()