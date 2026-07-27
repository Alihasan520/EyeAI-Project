from typing import List
import pandas as pd


def aggregate_predictions(df: pd.DataFrame, group_cols: List[str], prob_col: str = "prob_amd") -> pd.DataFrame:
    required = set(group_cols + [prob_col])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for aggregation: {missing}")

    agg_spec = {prob_col: "mean"}
    if "binary_label" in df.columns:
        agg_spec["binary_label"] = "max"
    if "label" in df.columns:
        agg_spec["label"] = "max"

    out = df.groupby(group_cols, as_index=False).agg(agg_spec)
    return out
