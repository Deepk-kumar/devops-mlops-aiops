"""Features ek jagah define: training aur drift detection dono yahi use karenge."""

NUMERIC = ["tenure", "monthly_charges", "total_charges", "support_tickets", "senior_citizen"]
CATEGORICAL = ["contract", "internet_service", "payment_method", "tech_support"]
FEATURES = NUMERIC + CATEGORICAL
TARGET = "churn"

CONTRACTS = ["Month-to-month", "One year", "Two year"]
INTERNET = ["DSL", "Fiber optic", "No"]
PAYMENT = ["Electronic check", "Mailed check", "Bank transfer", "Credit card"]
TECH_SUPPORT = ["Yes", "No", "No internet"]
