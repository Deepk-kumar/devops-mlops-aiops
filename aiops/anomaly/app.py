"""Anomaly detector service: har 30s Prometheus se metrics padho, Isolation Forest se score karo."""
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from aiops.anomaly.core import FEATURE_NAMES, AnomalyDetector, make_prometheus_fetch

SCORE = Gauge("churn_anomaly_score", "Anomaly score (bada = zyada anomalous)")
DETECTED = Gauge("churn_anomaly_detected", "1 agar latest point anomaly hai")
MAX_Z = Gauge("churn_anomaly_max_zscore", "Sabse zyada bhatakne wale metric ka robust z-score")
FEATURE_Z = Gauge("churn_anomaly_feature_zscore", "Robust z-score per metric", ["feature"])
WARMING = Gauge("churn_anomaly_warming_up", "1 jab tak model ke liye kaafi traffic data nahi")
TRAIN_POINTS = Gauge("churn_anomaly_train_points", "Training points")
LAST_RUN = Gauge("churn_anomaly_last_run_timestamp_seconds", "Last tick")
ERRORS = Counter("churn_anomaly_errors_total", "Tick errors (Prometheus unreachable etc.)")


class AnomalyService:
    def __init__(self, fetch, train_minutes: float = 120, holdout_minutes: float = 10,
                 retrain_seconds: float = 600, min_points: int = 20, contamination: float = 0.02):
        self.fetch = fetch
        self.train_minutes = train_minutes
        self.holdout_minutes = holdout_minutes
        self.retrain_seconds = retrain_seconds
        self.detector = AnomalyDetector(min_points=min_points, contamination=contamination)
        self._last_fit = 0.0
        self.last_result: dict = {"status": "starting"}

    def tick(self) -> dict:
        df = self.fetch(self.train_minutes)
        LAST_RUN.set(time.time())
        if df is None or df.empty:
            self.last_result = {"status": "no_data"}
            return self.last_result

        latest = df.iloc[-1]
        if not self.detector.ready or time.monotonic() - self._last_fit > self.retrain_seconds:
            # Latest window training se bahar: taaki abhi ka anomaly "normal" na seekh liya jaye
            train = df[df.index <= df.index[-1] - self.holdout_minutes * 60]
            if self.detector.fit(train):
                self._last_fit = time.monotonic()

        score, anomalous, state, details = self.detector.score(latest)
        SCORE.set(score)
        MAX_Z.set(details.get("max_z", 0.0))
        for f, v in details.get("zscores", {}).items():
            FEATURE_Z.labels(f).set(v)
        DETECTED.set(1 if anomalous else 0)
        WARMING.set(0 if self.detector.ready else 1)
        TRAIN_POINTS.set(self.detector.train_points)
        self.last_result = {
            "status": state, "score": score, "detail": details, "train_points": self.detector.train_points,
            "latest": {f: round(float(latest[f]), 4) for f in FEATURE_NAMES},
        }
        return self.last_result


def _loop(svc: AnomalyService, interval: float, stop: threading.Event):
    while not stop.is_set():
        try:
            svc.tick()
        except Exception as e:
            ERRORS.inc()
            svc.last_result = {"status": "error", "error": str(e)}
        stop.wait(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    prom = os.getenv("PROMETHEUS_URL", "http://kps-prometheus.monitoring.svc.cluster.local:9090")
    app.state.svc = AnomalyService(
        make_prometheus_fetch(prom),
        train_minutes=float(os.getenv("TRAIN_MINUTES", "120")),
        holdout_minutes=float(os.getenv("HOLDOUT_MINUTES", "10")),
        min_points=int(os.getenv("MIN_TRAIN_POINTS", "20")),
    )
    stop = threading.Event()
    if os.getenv("ANOMALY_LOOP", "true").lower() == "true":
        threading.Thread(target=_loop, args=(app.state.svc, float(os.getenv("INTERVAL_SECONDS", "30")), stop),
                         daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Anomaly Detector", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    return app.state.svc.last_result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
