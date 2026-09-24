# Build context = repo root:  docker build -f serving/Dockerfile .
# Stage 1: data generate + model train (reproducible, seed fixed)
FROM python:3.12-slim AS trainer
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ml ./ml
ARG MODEL_VERSION=v1
RUN python -m ml.src.generate_data --out ml/data/train.csv \
 && python -m ml.src.train --data ml/data/train.csv --out ml/models --version ${MODEL_VERSION}

# Stage 2: chhota runtime image
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/Deepk-kumar/devops-mlops-aiops"
ENV PYTHONUNBUFFERED=1 MODEL_DIR=/app/ml/models
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY serving ./serving
COPY --from=trainer /src/ml/models ./ml/models
USER 10001
EXPOSE 8000
CMD ["uvicorn", "serving.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
