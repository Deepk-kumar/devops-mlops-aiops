"""Evidently se data drift nikalo: reference (training) data vs current (live) data."""
import warnings
from pathlib import Path

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

from ml.src.schema import CATEGORICAL, FEATURES, NUMERIC

warnings.filterwarnings("ignore")
_DEFINITION = DataDefinition(numerical_columns=NUMERIC, categorical_columns=CATEGORICAL)


def _is_drifted(method: str, score: float, threshold: float) -> bool:
    # p-value wale tests me chhota score = drift; distance wale tests me bada score = drift
    if "p_value" in method.lower() or "p-value" in method.lower():
        return score < threshold
    return score > threshold


def compute_drift(reference: pd.DataFrame, current: pd.DataFrame, save_html: str | Path | None = None) -> dict:
    ref = Dataset.from_pandas(reference[FEATURES], data_definition=_DEFINITION)
    cur = Dataset.from_pandas(current[FEATURES], data_definition=_DEFINITION)
    snapshot = Report([DataDriftPreset()]).run(cur, ref)
    if save_html:
        snapshot.save_html(str(save_html))

    features = {}
    for metric in snapshot.dict()["metrics"]:
        cfg = metric["config"]
        if cfg["type"].endswith("ValueDrift"):
            score = float(metric["value"])
            features[cfg["column"]] = {
                "score": round(score, 4),
                "threshold": cfg["threshold"],
                "method": cfg["method"],
                "drifted": _is_drifted(cfg["method"], score, cfg["threshold"]),
            }

    drifted = sorted(f for f, v in features.items() if v["drifted"])
    share = len(drifted) / len(features) if features else 0.0
    return {
        "share": round(share, 4),
        "drifted_features": drifted,
        "dataset_drift": share >= 0.5,  # Evidently ka default rule
        "features": features,
    }
