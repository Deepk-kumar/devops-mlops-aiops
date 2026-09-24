# Self-Healing ML Platform (k3s + Terraform + ArgoCD)

Churn prediction model ke saath DevOps + MLOps + AIOps platform.
**Phase 1:** k3s cluster, MinIO (S3), PostgreSQL, ArgoCD.

## Prerequisites
- Ubuntu / Debian Linux ya **WSL2 Ubuntu** (16 GB RAM recommended)
- `ansible`, `terraform` (>= 1.5), `kubectl`, `make`, `git`

## Steps

```bash
# 1. k3s install (sudo password puchega)
make k3s

# 2. Cluster check
KUBECONFIG=ansible/kubeconfig kubectl get nodes

# 3. Terraform
make tf-init
make tf-apply          # "yes" likho, 3-6 minute lagte hain

# 4. Verify
make status            # platform + argocd namespace ke pods Running hone chahiye
```

## Access

| Service | Command | URL |
|---|---|---|
| ArgoCD | `make argocd-ui` | http://localhost:8080 (user: `admin`, pass: `make argocd-password`) |
| MinIO | `make minio-ui` | http://localhost:9001 (user: `minioadmin`, pass: `cd terraform && terraform output -raw minio_root_password`) |
| PostgreSQL | in-cluster | `postgres.platform.svc.cluster.local:5432` (DBs: `mlflow`, `airflow`) |

MinIO me ye buckets ban jayenge: `dvc-storage`, `mlflow-artifacts`, `models`.

## Troubleshooting
- **Pod Pending:** `kubectl -n platform describe pod <name>`, aksar RAM/storage ka issue hota hai.
- **MinIO chart error:** `helm repo add minio https://charts.min.io && helm search repo minio/minio`, phir `minio_chart_version` variable me version daalo.
- **Reset:** `make tf-destroy`. Poora cluster hatane ke liye: `/usr/local/bin/k3s-uninstall.sh`

## Next phases
2. Churn model + FastAPI serving  3. GitHub Actions + ArgoCD app  4. MLflow, DVC, Airflow
5. Prometheus/Loki/Grafana  6. Drift + anomaly detection  7. Auto-remediation  8. Ollama RCA agent

---
## OpenStack VM ke saath (Terraform se VM banana)

```bash
source openrc.sh                                   # OpenStack credentials
cp infra/openstack/terraform.tfvars.example infra/openstack/terraform.tfvars   # edit karo
make infra-init && make infra-apply                # VM + keypair + SG + floating IP
make k3s-remote                                    # Ansible VM par k3s lagata hai (sudo password nahi)
make tf-init && make tf-apply                      # MinIO, Postgres, ArgoCD
```
- Login SSH key se hota hai (`terraform output ssh_command`). Password optional hai: `vm_password` variable.
- `allowed_cidr` me apna IP/32 daalo, taaki 22 aur 6443 sabke liye khule na rahein.
- VM hatane ke liye: `make infra-destroy`

---
## Phase 2: churn model + FastAPI + CI/CD + ArgoCD

```
git push -> GitHub Actions (test -> docker build -> GHCR push -> values.yaml tag update)
         -> ArgoCD (repo watch) -> k3s (namespace: mlops) -> churn-api pods
```

Local test (laptop par):
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
make test          # 6 tests
make train         # ml/models/model.joblib
MODEL_DIR=ml/models uvicorn serving.app.main:app --port 8000
```

Cluster par deploy:
```bash
make deploy-app    # ArgoCD Application banata hai (ek baar)
make api-forward   # terminal 1  -> localhost:8000
make api-test      # terminal 2  -> prediction JSON
curl localhost:8000/metrics | grep churn_
```

Endpoints: `/health`, `/ready`, `/predict`, `/metrics`, `/docs`.
`--drift` flag se `python3 -m ml.src.generate_data --drift` drifted data banta hai (Phase 6).

---
## Phase 5: Monitoring (Prometheus, Grafana, Alertmanager, Loki)

```bash
make tf-apply          # monitoring module deploy (5-10 min)
make grafana-ui        # http://localhost:3000  (admin / terraform -chdir=terraform output -raw grafana_password)
make prometheus-ui     # http://localhost:9090  -> Status > Targets me churn-api UP
make alertmanager-ui   # http://localhost:9093
make api-forward       # terminal 1
make traffic           # terminal 2 (dashboard me data aayega)
```
Dashboard "Churn API" ArgoCD se aata hai (`gitops/charts/churn-api/dashboards`).
Alert rules: `ChurnApiDown`, `ChurnApiHighLatency`, `ChurnApiHighErrorRate`, `ChurnApiPodRestarting`.
`make traffic-drift` drifted inputs bhejta hai (Grafana ke "Input drift signals" panel me monthly_charges upar jata dikhega).
