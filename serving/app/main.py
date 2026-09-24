"""Churn prediction API + Prometheus metrics (+ optional chaos endpoints demo ke liye)."""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

# ---------------- Metrics ----------------
REQUESTS = Counter("churn_api_requests_total", "HTTP requests", ["endpoint", "method", "status"])
LATENCY = Histogram(
    "churn_api_request_latency_seconds",
    "Request latency",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
PREDICTIONS = Counter("churn_predictions_total", "Predictions by label", ["label"])
PROBABILITY = Histogram(
    "churn_prediction_probability", "Churn probability", buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)
# Input distribution: drift ka pehla signal
IN_MONTHLY = Histogram(
    "churn_input_monthly_charges", "monthly_charges inputs", buckets=(20, 40, 60, 80, 100, 120, 150, 200)
)
IN_TENURE = Histogram("churn_input_tenure_months", "tenure inputs", buckets=(6, 12, 24, 36, 48, 60, 72))
MODEL_INFO = Gauge("churn_model_info", "Loaded model", ["version"])


# ---------------- Schema ----------------
class Customer(BaseModel):
    tenure: int = Field(ge=0, le=100, examples=[5])
    monthly_charges: float = Field(ge=0, examples=[85.5])
    total_charges: float = Field(ge=0, examples=[430.0])
    support_tickets: int = Field(ge=0, examples=[2])
    senior_citizen: int = Field(ge=0, le=1, examples=[0])
    contract: Literal["Month-to-month", "One year", "Two year"]
    internet_service: Literal["DSL", "Fiber optic", "No"]
    payment_method: Literal["Electronic check", "Mailed check", "Bank transfer", "Credit card"]
    tech_support: Literal["Yes", "No", "No internet"]


class Prediction(BaseModel):
    churn_probability: float
    churn_prediction: bool
    model_version: str


# ---------------- App ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    model_dir = Path(os.getenv("MODEL_DIR", "ml/models"))
    app.state.model = None
    app.state.version = "none"
    if (model_dir / "model.joblib").exists():
        app.state.model = joblib.load(model_dir / "model.joblib")
        meta = json.loads((model_dir / "metrics.json").read_text())
        app.state.version = meta.get("version", "unknown")
        MODEL_INFO.labels(version=app.state.version).set(1)
    yield


app = FastAPI(title="Churn Prediction API", lifespan=lifespan)


@app.middleware("http")
async def track(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    endpoint = route.path if route else "unmapped"
    if endpoint != "/metrics":
        LATENCY.labels(endpoint).observe(time.perf_counter() - start)
        REQUESTS.labels(endpoint, request.method, str(response.status_code)).inc()
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ready", "model_version": app.state.version}


@app.post("/predict", response_model=Prediction)
def predict(customer: Customer):
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="model not loaded")

    row = pd.DataFrame([customer.model_dump()])
    proba = float(app.state.model.predict_proba(row)[0, 1])
    label = proba >= 0.5

    PREDICTIONS.labels("churn" if label else "stay").inc()
    PROBABILITY.observe(proba)
    IN_MONTHLY.observe(customer.monthly_charges)
    IN_TENURE.observe(customer.tenure)

    return Prediction(churn_probability=round(proba, 4), churn_prediction=label, model_version=app.state.version)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------- Chaos (sirf CHAOS_ENABLED=true par) ----------------
# Phase 7 me self-healing demo ke liye: latency spike, errors, crash inject karo.
if os.getenv("CHAOS_ENABLED", "false").lower() == "true":

    @app.get("/chaos/slow")
    async def chaos_slow(ms: int = 2000):
        await asyncio.sleep(min(ms, 30000) / 1000)
        return {"slept_ms": ms}

    @app.get("/chaos/error")
    def chaos_error():
        raise HTTPException(status_code=500, detail="injected failure")

    @app.get("/chaos/crash")
    def chaos_crash():
        os._exit(1)
