"""Telco-style synthetic churn data.

Kaggle account ke bina reproducible data milta hai (seed fixed).
`--drift` se aisa data banta hai jisme customers ka behaviour badal gaya ho
(mehnge plans, kam tenure, zyada tickets) -> Phase 6 me drift demo ke liye.
Asli Telco CSV use karni ho to same column names me rakh do.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src.schema import CONTRACTS, INTERNET, PAYMENT


def generate(n: int = 7000, seed: int = 42, drift: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    contract = rng.choice(CONTRACTS, n, p=[0.55, 0.21, 0.24])
    internet = rng.choice(INTERNET, n, p=[0.25, 0.60, 0.15] if drift else [0.34, 0.44, 0.22])
    payment = rng.choice(PAYMENT, n, p=[0.34, 0.23, 0.22, 0.21])
    senior = rng.binomial(1, 0.16, n)
    tenure = np.clip(rng.exponential(14 if drift else 28, n), 1, 72).astype(int)

    base = np.select([internet == "DSL", internet == "Fiber optic"], [45.0, 80.0], default=20.0)
    monthly = np.clip(base + rng.normal(0, 8, n), 18, None)
    if drift:
        monthly = monthly * 1.6
    total = monthly * tenure * rng.uniform(0.95, 1.05, n)

    tech = np.where(internet == "No", "No internet", np.where(rng.random(n) < 0.4, "Yes", "No"))
    tickets = rng.poisson(1.6 if drift else 1.0, n)

    logit = (
        -1.6
        + 1.5 * (contract == "Month-to-month")
        - 1.0 * (contract == "Two year")
        - 0.035 * tenure
        + 0.02 * (monthly - 65)
        + 0.5 * (internet == "Fiber optic")
        + 0.25 * senior
        - 0.5 * (tech == "Yes")
        + 0.3 * tickets
        + 0.4 * (payment == "Electronic check")
    )
    churn = rng.random(n) < 1 / (1 + np.exp(-logit))

    return pd.DataFrame(
        {
            "tenure": tenure,
            "monthly_charges": monthly.round(2),
            "total_charges": total.round(2),
            "support_tickets": tickets,
            "senior_citizen": senior,
            "contract": contract,
            "internet_service": internet,
            "payment_method": payment,
            "tech_support": tech,
            "churn": churn.astype(int),
        }
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ml/data/train.csv")
    ap.add_argument("--n", type=int, default=7000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--drift", action="store_true")
    a = ap.parse_args()

    df = generate(a.n, a.seed, a.drift)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"{len(df)} rows -> {a.out} | churn rate {df['churn'].mean():.1%} | drift={a.drift}")
