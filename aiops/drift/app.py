"""Drift detector service.

  serving pods --POST /ingest--> is service (memory me rolling window)
  har INTERVAL_SECONDS: Evidently se drift nikalta hai -> Prometheus gauges + HTML report
"""
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel

from aiops.drift.core import compute_drift
from ml.src.generate_data import generate
from ml.src.schema import FEATURES

SHARE = Gauge("churn_drift_share", "Share of features with drift (0-1)")
DETECTED = Gauge("churn_drift_detected", "1 if >=50% features drifted")
FEATURE_SCORE = Gauge("churn_drift_feature_score", "Drift score per feature", ["feature"])
FEATURE_DRIFTED = Gauge("churn_drift_feature_detected", "1 if feature drifted", ["feature"])
ROWS = Gauge("churn_drift_current_rows", "Rows in current window")
INSUFFICIENT = Gauge("churn_drift_insufficient_data", "1 if too few rows to judge")
LAST_RUN = Gauge("churn_drift_last_run_timestamp_seconds", "Last drift run")
INGESTED = Counter("churn_drift_ingested_total", "Records received")
ERRORS = Counter("churn_drift_errors_total", "Drift run errors")


class DriftService:
    def __init__(self, reference: pd.DataFrame | None = None, window_minutes: float = 15,
                 min_rows: int = 500, max_rows: int = 20000, report_path: str = "/tmp/drift_report.html"):
        self._reference = reference
        self.window_minutes = window_minutes
        self.min_rows = min_rows
        self.report_path = report_path
        self._rows: deque = deque(maxlen=max_rows)
        self._lock = threading.Lock()
        self.last_result: dict = {"status": "no_data_yet"}

    @classmethod
    def from_env(cls) -> "DriftService":
        return cls(
            window_minutes=float(os.getenv("WINDOW_MINUTES", "15")),
            min_rows=int(os.getenv("MIN_ROWS", "500")),
            report_path=os.getenv("REPORT_PATH", "/tmp/drift_report.html"),
        )

    @property
    def reference(self) -> pd.DataFrame:
        if self._reference is None:
            path = Path(os.getenv("REFERENCE_CSV", "ml/data/reference.csv"))
            self._reference = pd.read_csv(path) if path.exists() else generate()
        return self._reference

    def add(self, records: list[dict]) -> int:
        now, n = time.time(), 0
        with self._lock:
            for r in records:
                if all(f in r for f in FEATURES):
                    self._rows.append((float(r.get("ts", now)), {f: r[f] for f in FEATURES}))
                    n += 1
        INGESTED.inc(n)
        return n

    def current_frame(self) -> pd.DataFrame:
        cutoff = time.time() - self.window_minutes * 60
        with self._lock:
            rows = [row for ts, row in self._rows if ts >= cutoff]
        return pd.DataFrame(rows, columns=FEATURES)

    def run_once(self) -> dict:
        cur = self.current_frame()
        ROWS.set(len(cur))
        LAST_RUN.set(time.time())

        if len(cur) < self.min_rows:
            # Data kam hai (ya traffic ruk gaya): purana alert resolve ho jaye
            INSUFFICIENT.set(1)
            SHARE.set(0)
            DETECTED.set(0)
            self.last_result = {"status": "insufficient_data", "rows": len(cur), "min_rows": self.min_rows}
            return self.last_result

        INSUFFICIENT.set(0)
        res = compute_drift(self.reference, cur, save_html=self.report_path)
        SHARE.set(res["share"])
        DETECTED.set(1 if res["dataset_drift"] else 0)
        for name, v in res["features"].items():
            FEATURE_SCORE.labels(name).set(v["score"])
            FEATURE_DRIFTED.labels(name).set(1 if v["drifted"] else 0)
        self.last_result = {"status": "ok", "rows": len(cur), "computed_at": time.time(), **res}
        return self.last_result


class Batch(BaseModel):
    records: list[dict]


def _loop(svc: DriftService, interval: float, stop: threading.Event):
    while not stop.wait(interval):
        try:
            svc.run_once()
        except Exception as e:  # loop kabhi marna nahi chahiye
            ERRORS.inc()
            svc.last_result = {"status": "error", "error": str(e)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.svc = DriftService.from_env()
    stop = threading.Event()
    if os.getenv("DRIFT_LOOP", "true").lower() == "true":
        threading.Thread(
            target=_loop, args=(app.state.svc, float(os.getenv("INTERVAL_SECONDS", "60")), stop), daemon=True
        ).start()
    yield
    stop.set()


app = FastAPI(title="Drift Detector", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(batch: Batch):
    return {"accepted": app.state.svc.add(batch.records)}


@app.post("/run")
def run_now():
    return app.state.svc.run_once()


@app.get("/status")
def status():
    svc: DriftService = app.state.svc
    return {**svc.last_result, "buffered_rows": len(svc._rows), "window_minutes": svc.window_minutes}


@app.get("/report")
def report():
    p = Path(app.state.svc.report_path)
    if not p.exists():
        raise HTTPException(404, "report abhi nahi bana (min rows ka wait)")
    return FileResponse(p, media_type="text/html")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
