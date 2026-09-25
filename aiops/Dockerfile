# Build context = repo root:  docker build -f aiops/Dockerfile .
# Ek image, do services: drift-detector (default CMD) aur anomaly-detector (chart me command override)
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/Deepk-kumar/devops-mlops-aiops"
ENV PYTHONUNBUFFERED=1 PYTHONWARNINGS=ignore
WORKDIR /app
COPY aiops/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ml ./ml
COPY aiops ./aiops
# Reference data = wahi jo model training me use hota hai (seed fixed)
RUN python -m ml.src.generate_data --out /app/ml/data/reference.csv
ENV REFERENCE_CSV=/app/ml/data/reference.csv
USER 10001
EXPOSE 8000
CMD ["uvicorn", "aiops.drift.app:app", "--host", "0.0.0.0", "--port", "8000"]
