"""Churn model train karo aur model.joblib + metrics.json + reference.csv save karo."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.src.schema import CATEGORICAL, FEATURES, NUMERIC, TARGET


def build_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )
    return Pipeline([("pre", pre), ("clf", GradientBoostingClassifier(random_state=42))])


def train(df: pd.DataFrame, out_dir, version: str = "v1") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURES], df[TARGET], test_size=0.2, random_state=42, stratify=df[TARGET]
    )
    model = build_pipeline().fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "version": version,
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "accuracy": round(float(accuracy_score(y_test, proba > 0.5)), 4),
        "f1": round(float(f1_score(y_test, proba > 0.5)), 4),
        "n_train": int(len(X_train)),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": FEATURES,
    }

    joblib.dump(model, out / "model.joblib")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    # Drift detection (Phase 6) isko "reference" data ki tarah use karega
    X_train.assign(**{TARGET: y_train}).to_csv(out / "reference.csv", index=False)
    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ml/data/train.csv")
    ap.add_argument("--out", default="ml/models")
    ap.add_argument("--version", default=os.getenv("MODEL_VERSION", "v1"))
    a = ap.parse_args()

    m = train(pd.read_csv(a.data), a.out, a.version)
    print(json.dumps(m, indent=2))
