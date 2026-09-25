import numpy as np
import pandas as pd

from aiops.anomaly.app import AnomalyService
from aiops.anomaly.core import FEATURE_NAMES, AnomalyDetector, parse_matrix


def baseline(n=60, seed=0):
    r = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "rps": r.normal(5, 0.4, n),
            "p95_latency": r.normal(0.03, 0.004, n),
            "error_ratio": np.zeros(n),
            "cpu_cores": r.normal(0.12, 0.02, n),
            "memory_mb": r.normal(300, 4, n),
        },
        index=np.arange(n) * 30.0,
    )


def row(**over):
    base = {"rps": 5.0, "p95_latency": 0.03, "error_ratio": 0.0, "cpu_cores": 0.12, "memory_mb": 300.0}
    return pd.Series({**base, **over})


def test_parse_matrix_handles_nan_and_empty():
    resp = {"data": {"result": [{"values": [[1, "0.5"], [2, "NaN"]]}]}}
    s = parse_matrix(resp)
    assert len(s) == 2 and s.iloc[0] == 0.5 and np.isnan(s.iloc[1])
    assert parse_matrix({"data": {"result": []}}).empty


def test_detector_flags_single_metric_spikes_not_normal():
    d = AnomalyDetector(min_points=20)
    assert d.score(row())[2] == "warming_up"
    assert d.fit(baseline())

    assert d.score(row())[1] is False                                   # normal
    for spike in (row(p95_latency=1.5), row(error_ratio=0.5), row(cpu_cores=1.2, rps=60)):
        score, anomalous, state, detail = d.score(spike)
        assert anomalous and state == "anomaly" and detail["zscore"]
    assert d.score(row(p95_latency=1.5))[3]["worst_feature"] == "p95_latency"
    assert d.score(row(rps=0.0))[2] == "idle"                           # traffic nahi -> alert nahi


def test_iforest_catches_multivariate_pattern_zscore_misses():
    # latency load ke saath badhti hai; "kam load par zyada latency" har metric akele normal range me hai
    r = np.random.default_rng(1)
    n = 200
    rps = r.uniform(2, 10, n)
    df = pd.DataFrame(
        {
            "rps": rps,
            "p95_latency": 0.02 + 0.002 * rps + r.normal(0, 0.002, n),
            "error_ratio": np.zeros(n),
            "cpu_cores": 0.02 * rps + r.normal(0, 0.01, n),
            "memory_mb": r.normal(300, 4, n),
        },
        index=np.arange(n) * 30.0,
    )
    d = AnomalyDetector(min_points=20)
    d.fit(df)
    ok = row(rps=6.0, p95_latency=0.032, cpu_cores=0.12)
    odd = row(rps=2.0, p95_latency=0.05, cpu_cores=0.04)
    assert d.score(ok)[1] is False
    _, anomalous, _, detail = d.score(odd)
    assert anomalous and detail["iforest"] and not detail["zscore"]


def test_idle_history_does_not_train():
    idle = baseline()
    idle["rps"] = 0.0
    assert AnomalyDetector(min_points=20).fit(idle) is False


def test_service_warmup_then_detects():
    hist = baseline(80)
    svc = AnomalyService(lambda m: hist, holdout_minutes=10, min_points=20)
    assert svc.tick()["status"] in ("normal", "anomaly")

    spike = hist.copy()
    spike.iloc[-1] = row(p95_latency=2.0).values
    svc2 = AnomalyService(lambda m: spike, holdout_minutes=10, min_points=20)
    res = svc2.tick()
    assert res["status"] == "anomaly" and res["detail"]["worst_feature"] == "p95_latency"

    short = baseline(30)   # holdout ke baad kaafi points nahi -> warming_up
    svc3 = AnomalyService(lambda m: short, holdout_minutes=10, min_points=25)
    assert svc3.tick()["status"] == "warming_up"


def test_feature_names_stable():
    assert FEATURE_NAMES == ["rps", "p95_latency", "error_ratio", "cpu_cores", "memory_mb"]
