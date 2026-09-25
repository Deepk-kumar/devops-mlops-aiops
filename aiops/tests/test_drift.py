import pytest
from fastapi.testclient import TestClient

from aiops.drift.app import DriftService, app
from aiops.drift.core import compute_drift
from ml.src.generate_data import generate
from ml.src.schema import FEATURES


@pytest.fixture(scope="module")
def reference():
    return generate(n=7000, seed=42)[FEATURES]


def test_no_drift_on_normal_data(reference):
    res = compute_drift(reference, generate(n=500, seed=7)[FEATURES])
    assert set(res["features"]) == set(FEATURES)
    assert res["share"] < 0.25
    assert res["dataset_drift"] is False


def test_detects_drifted_data(reference):
    res = compute_drift(reference, generate(n=500, seed=7, drift=True)[FEATURES])
    assert res["share"] >= 0.25
    assert "monthly_charges" in res["drifted_features"]
    assert "tenure" in res["drifted_features"]


def test_service_end_to_end(reference, monkeypatch, tmp_path):
    monkeypatch.setenv("MIN_ROWS", "100")
    monkeypatch.setenv("DRIFT_LOOP", "false")
    monkeypatch.setenv("REPORT_PATH", str(tmp_path / "r.html"))
    with TestClient(app) as c:
        c.app.state.svc._reference = reference

        assert c.get("/report").status_code == 404

        drifted = generate(n=300, seed=5, drift=True)[FEATURES].to_dict("records")
        assert c.post("/ingest", json={"records": drifted}).json() == {"accepted": 300}
        # feature adhoora ho to record ignore
        assert c.post("/ingest", json={"records": [{"tenure": 1}]}).json() == {"accepted": 0}

        res = c.post("/run").json()
        assert res["status"] == "ok" and res["share"] >= 0.25
        assert c.get("/report").status_code == 200
        body = c.get("/metrics").text
        assert "churn_drift_share" in body and 'churn_drift_feature_detected{feature="monthly_charges"} 1.0' in body


def test_insufficient_data_resets_alert(reference):
    svc = DriftService(reference=reference, min_rows=200)
    svc.add(generate(n=10, seed=1)[FEATURES].to_dict("records"))
    res = svc.run_once()
    assert res["status"] == "insufficient_data"
