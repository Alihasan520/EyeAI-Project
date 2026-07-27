from typing import List

import numpy as np
import pandas as pd


def _validate_prediction_frame(dataframe: pd.DataFrame, prob_col: str):
    required = {"image_id", prob_col}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise KeyError(f"Prediction dataframe is missing columns: {missing}")
    if dataframe["image_id"].astype(str).duplicated().any():
        duplicates = dataframe.loc[dataframe["image_id"].astype(str).duplicated(), "image_id"].astype(str).head(20).tolist()
        raise ValueError(f"Prediction dataframe contains duplicate image_id values: {duplicates}")


def weighted_average_predictions(
    prediction_dfs: List[pd.DataFrame],
    weights: List[float],
    prob_col: str = "prob_amd",
) -> pd.DataFrame:
    """Average prediction files after exact image_id alignment."""
    if len(prediction_dfs) != len(weights):
        raise ValueError("Number of prediction dataframes must match number of weights.")
    if not prediction_dfs:
        raise ValueError("At least one prediction dataframe is required.")

    weights_array = np.asarray(weights, dtype=float)
    if np.isclose(weights_array.sum(), 0):
        raise ValueError("Ensemble weights sum to zero.")
    weights_array = weights_array / weights_array.sum()

    for dataframe in prediction_dfs:
        _validate_prediction_frame(dataframe, prob_col)

    base = prediction_dfs[0].copy()
    base["image_id"] = base["image_id"].astype(str)
    base_ids = base["image_id"].tolist()
    base_id_set = set(base_ids)

    metadata_columns = [
        column
        for column in ["image_id", "image_name", "patient_id", "eye", "label", "binary_label", "dataset_source"]
        if column in base.columns
    ]
    output = base[metadata_columns].copy()
    combined = np.zeros(len(base), dtype=float)

    for index, (dataframe, weight) in enumerate(zip(prediction_dfs, weights_array)):
        current = dataframe.copy()
        current["image_id"] = current["image_id"].astype(str)
        current_ids = set(current["image_id"])
        if current_ids != base_id_set:
            missing = sorted(base_id_set - current_ids)[:20]
            extra = sorted(current_ids - base_id_set)[:20]
            raise ValueError(
                f"Prediction image_id mismatch for model {index}. Missing={missing}, extra={extra}"
            )

        aligned = current.set_index("image_id").loc[base_ids]
        if "binary_label" in base.columns and "binary_label" in aligned.columns:
            expected = base["binary_label"].astype(int).to_numpy()
            observed = aligned["binary_label"].astype(int).to_numpy()
            if not np.array_equal(expected, observed):
                raise ValueError(f"binary_label mismatch after image_id alignment for model {index}.")
        combined += aligned[prob_col].astype(float).to_numpy() * float(weight)

    output[prob_col] = combined
    return output


def tune_two_model_weights(df_a: pd.DataFrame, df_b: pd.DataFrame, metric_fn, grid_step: float = 0.05):
    best = None
    rows = []
    for weight_a in np.arange(0.0, 1.0 + grid_step / 2.0, grid_step):
        weight_b = 1.0 - weight_a
        combined = weighted_average_predictions([df_a, df_b], [weight_a, weight_b])
        result = metric_fn(combined)
        row = {"weight_model_a": float(weight_a), "weight_model_b": float(weight_b), **result}
        rows.append(row)
        score = float(result.get("score", result.get("macro_f1", -1e9)))
        if best is None or score > best["score"]:
            best = {
                "score": score,
                "weight_model_a": float(weight_a),
                "weight_model_b": float(weight_b),
                "result": result,
            }
    return best, pd.DataFrame(rows)
