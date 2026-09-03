from __future__ import annotations

import polars as pl


def print_shape_and_columns(data_frame: pl.DataFrame, label: str = "DataFrame") -> None:
    """
    Small helper utils
    Prints the shape and columns of a Polars DataFrame.
    """
    print(f"{label} shape: {data_frame.shape}")
    print(f"{label} columns:")
    for col in data_frame.columns:
        print(f"  - {col}")