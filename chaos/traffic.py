"""Churn API par traffic bhejo (dashboard demo, drift demo, load).

  python3 chaos/traffic.py                       # normal traffic
  python3 chaos/traffic.py --drift               # drifted inputs (Phase 6 me drift alert)
  python3 chaos/traffic.py --rps 20 --duration 300
  python3 chaos/traffic.py --slow-ms 1500        # /chaos/slow (CHAOS_ENABLED=true chahiye)

Sirf standard library, kuch install nahi karna.
"""
import argparse
import json
import random
import time
import urllib.error
import urllib.request

CONTRACTS = ["Month-to-month", "One year", "Two year"]
INTERNET = ["DSL", "Fiber optic", "No"]
PAYMENT = ["Electronic check", "Mailed check", "Bank transfer", "Credit card"]


def customer(drift: bool) -> dict:
    internet = random.choices(INTERNET, [0.25, 0.60, 0.15] if drift else [0.34, 0.44, 0.22])[0]
    base = {"DSL": 45, "Fiber optic": 80, "No": 20}[internet]
    monthly = max(18, random.gauss(base, 8)) * (1.6 if drift else 1.0)
    tenure = max(1, min(72, int(random.expovariate(1 / (14 if drift else 28)))))
    return {
        "tenure": tenure,
        "monthly_charges": round(monthly, 2),
        "total_charges": round(monthly * tenure, 2),
        "support_tickets": min(10, int(random.expovariate(1 / (1.6 if drift else 1.0)))),
        "senior_citizen": int(random.random() < 0.16),
        "contract": random.choices(CONTRACTS, [0.55, 0.21, 0.24])[0],
        "internet_service": internet,
        "payment_method": random.choice(PAYMENT),
        "tech_support": "No internet" if internet == "No" else random.choice(["Yes", "No"]),
    }


def call(url: str, body: dict | None = None) -> int:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--rps", type=float, default=5)
    ap.add_argument("--duration", type=int, default=120, help="seconds")
    ap.add_argument("--drift", action="store_true")
    ap.add_argument("--slow-ms", type=int, default=0)
    a = ap.parse_args()

    counts: dict[int, int] = {}
    end = time.time() + a.duration
    print(f"traffic -> {a.url} | {a.rps} rps | {a.duration}s | drift={a.drift} | slow_ms={a.slow_ms}")
    while time.time() < end:
        t0 = time.time()
        if a.slow_ms and random.random() < 0.5:
            code = call(f"{a.url}/chaos/slow?ms={a.slow_ms}")
        else:
            code = call(f"{a.url}/predict", customer(a.drift))
        counts[code] = counts.get(code, 0) + 1
        time.sleep(max(0, 1 / a.rps - (time.time() - t0)))
    print("status codes:", counts)
