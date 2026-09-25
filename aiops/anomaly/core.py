"""Prometheus metrics par Isolation Forest se anomaly detection."""
import json
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# /predict + /chaos/* (health probes ka baseline traffic ginte nahi)
_EP = 'endpoint=~"/predict|/chaos/.*"'
QUERIES = {
    "rps": f"sum(rate(churn_api_requests_total{{{_EP}}}[1m]))",
    "p95_latency": f"histogram_quantile(0.95, sum by (le) (rate(churn_api_request_latency_seconds_bucket{{{_EP}}}[1m])))",
    "error_ratio": f'sum(rate(churn_api_requests_total{{{_EP},status=~"5.."}}[1m])) / sum(rate(churn_api_requests_total{{{_EP}}}[1m]))',
    "cpu_cores": 'sum(rate(container_cpu_usage_seconds_total{namespace="mlops",container="api"}[1m]))',
    "memory_mb": 'sum(container_memory_working_set_bytes{namespace="mlops",container="api"}) / 1e6',
}
FEATURE_NAMES = list(QUERIES)

# Robust z-score ke liye har metric ka minimum "normal spread" (units me).
# Bina iske constant metric (jaise error_ratio = 0) me chhota sa jitter bhi bada z-score de deta.
MIN_SCALE = {"rps": 0.5, "p95_latency": 0.005, "error_ratio": 0.02, "cpu_cores": 0.02, "memory_mb": 10.0}


def parse_matrix(response: dict) -> pd.Series:
    """Prometheus query_range response -> Series(index=unix ts, values=float). NaN/empty safe."""
    result = response.get("data", {}).get("result", [])
    if not result:
        return pd.Series(dtype=float)
    values = result[0]["values"]
    return pd.Series([float(v) for _, v in values], index=[float(t) for t, _ in values])


def make_prometheus_fetch(base_url: str, step: int = 30):
    def fetch(minutes: float) -> pd.DataFrame:
        end = time.time()
        series = {}
        for name, query in QUERIES.items():
            qs = urllib.parse.urlencode({"query": query, "start": end - minutes * 60, "end": end, "step": step})
            with urllib.request.urlopen(f"{base_url}/api/v1/query_range?{qs}", timeout=10) as r:
                series[name] = parse_matrix(json.load(r))
        df = pd.concat(series, axis=1).sort_index()
        return df.reindex(columns=FEATURE_NAMES).fillna(0.0)

    return fetch


class AnomalyDetector:
    """Hybrid detector:
    - Isolation Forest: multi-metric pattern (jaise rps aur cpu ka rishta bigadna)
    - Robust z-score (median/MAD): ek metric ka bada spike. iForest training range ke bahar jaate hi
      saturate ho jata hai (p95=0.06s aur p95=1.5s ka score same aata hai), isliye ye zaruri hai.
    """

    def __init__(self, min_points: int = 20, contamination: float = 0.02, active_rps: float = 0.1,
                 z_threshold: float = 6.0):
        self.min_points = min_points
        self.contamination = contamination
        self.active_rps = active_rps
        self.z_threshold = z_threshold
        self.scaler: StandardScaler | None = None
        self.forest: IsolationForest | None = None
        self.center: pd.Series | None = None
        self.spread: pd.Series | None = None
        self.train_points = 0

    @property
    def ready(self) -> bool:
        return self.forest is not None

    def fit(self, df: pd.DataFrame) -> bool:
        # Sirf "traffic wale" points se seekho, warna idle (sab zero) baseline ban jata hai
        active = df[df["rps"] > self.active_rps][FEATURE_NAMES]
        if len(active) < self.min_points:
            return False
        self.center = active.median()
        mad = (active - self.center).abs().median() * 1.4826
        self.spread = pd.Series({f: max(float(mad[f]), MIN_SCALE[f]) for f in FEATURE_NAMES})
        self.scaler = StandardScaler().fit(active)
        z = self.scaler.transform(active)
        # Constant feature (jaise error_ratio hamesha 0) me isolate karne layak spread nahi hota,
        # isliye thoda noise: baad me 0 -> 0.5 jump outlier ban sake
        z = z + np.random.default_rng(42).normal(0, 0.05, z.shape)
        self.forest = IsolationForest(n_estimators=200, contamination=self.contamination, random_state=42).fit(z)
        self.train_points = len(active)
        return True

    def score(self, row) -> tuple[float, bool, str, dict]:
        """returns (iforest_score, is_anomaly, state, details). Score jitna bada, utna anomalous."""
        if not self.ready:
            return 0.0, False, "warming_up", {}
        if float(row["rps"]) <= self.active_rps:
            return 0.0, False, "idle", {}

        x = pd.DataFrame([[float(row[f]) for f in FEATURE_NAMES]], columns=FEATURE_NAMES)
        z = self.scaler.transform(x)
        raw = float(-self.forest.decision_function(z)[0])
        iforest_flag = bool(self.forest.predict(z)[0] == -1)

        zscores = {f: abs(float(row[f]) - float(self.center[f])) / float(self.spread[f]) for f in FEATURE_NAMES}
        worst = max(zscores, key=zscores.get)
        z_flag = zscores[worst] > self.z_threshold

        anomalous = iforest_flag or z_flag
        details = {
            "iforest": iforest_flag,
            "zscore": z_flag,
            "worst_feature": worst,
            "max_z": round(zscores[worst], 2),
            "zscores": {f: round(v, 2) for f, v in zscores.items()},
        }
        return round(raw, 4), anomalous, "anomaly" if anomalous else "normal", details
