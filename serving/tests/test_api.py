import os

import pytest
from fastapi.testclient import TestClient

from ml.src.generate_data import generate
from ml.src.train import train

RISKY = {
    "tenure": 2, "monthly_charges": 95.0, "total_charges": 190.0, "support_tickets": 3,
    "senior_citizen": 1, "contract": "Month-to-month", "internet_service": "Fiber optic",
    "payment_method": "Electronic check", "tech_support": "No",
}
SAFE = {
    "tenure": 60, "monthly_charges": 25.0, "total_charges": 1500.0, "support_tickets": 0,
    "senior_citizen": 0, "contract": "Two year", "internet_service": "DSL",
    "payment_method": "Credit card", "tech_support": "Yes",
}


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    model_dir = tmp_path_factory.mktemp("model")
    train(generate(n=2500, seed=1), model_dir, version="test")
    os.environ["MODEL_DIR"] = str(model_dir)

    from serving.app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_reports_model_version(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["model_version"] == "test"


def test_predict_ranks_risky_above_safe(client):
    risky = client.post("/predict", json=RISKY).json()
    safe = client.post("/predict", json=SAFE).json()
    assert 0 <= safe["churn_probability"] <= 1
    assert risky["churn_probability"] > safe["churn_probability"]


def test_predict_rejects_bad_input(client):
    bad = {**RISKY, "contract": "Weekly"}
    assert client.post("/predict", json=bad).status_code == 422


def test_metrics_exposed(client):
    client.post("/predict", json=RISKY)
    body = client.get("/metrics").text
    assert "churn_predictions_total" in body
    assert "churn_api_request_latency_seconds_bucket" in body
    assert 'churn_model_info{version="test"} 1.0' in body


def test_chaos_disabled_by_default(client):
    assert client.get("/chaos/error").status_code == 404
