"""Features ek jagah define: training aur drift detection dono yahi use karenge."""

NUMERIC = ["tenure", "monthly_charges", "total_charges", "support_tickets", "senior_citizen"]
CATEGORICAL = ["contract", "internet_service", "payment_method", "tech_support"]
FEATURES = NUMERIC + CATEGORICAL
TARGET = "churn"

CONTRACTS = ["Month-to-month", "One year", "Two year"]
INTERNET = ["DSL", "Fiber optic", "No"]
PAYMENT = ["Electronic check", "Mailed check", "Bank transfer", "Credit card"]
TECH_SUPPORT = ["Yes", "No", "No internet"]

# Prometheus histogram buckets (serving/app/main.py ke Histogram() se match karte hain).
# Drift detector inhi buckets ko reference stats se compare karta hai.
MONTHLY_CHARGES_BUCKETS = [20, 40, 60, 80, 100, 120, 150, 200]
TENURE_BUCKETS = [6, 12, 24, 36, 48, 60, 72]
