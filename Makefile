KUBECONFIG_FILE := ansible/kubeconfig

.PHONY: help infra-init infra-apply infra-destroy k3s-remote k3s tf-init tf-plan tf-apply tf-destroy status argocd-password argocd-ui minio-ui data train test deploy-app api-forward api-test grafana-ui prometheus-ui alertmanager-ui traffic traffic-drift

help:
	@echo "make k3s              - Ansible se k3s install karo"
	@echo "make tf-init          - Terraform init"
	@echo "make tf-plan          - Terraform plan"
	@echo "make tf-apply         - MinIO + Postgres + ArgoCD deploy karo"
	@echo "make tf-destroy       - Sab kuch hata do (cluster chhodkar)"
	@echo "make status           - Saare pods dekho"
	@echo "make argocd-password  - ArgoCD admin password"
	@echo "make argocd-ui        - ArgoCD UI -> http://localhost:8080"
	@echo "make minio-ui         - MinIO console -> http://localhost:9001"

k3s:
	cd ansible && ansible-playbook playbooks/k3s-install.yml -K

tf-init:
	cd terraform && terraform init

tf-plan:
	cd terraform && terraform plan

tf-apply:
	cd terraform && terraform apply

tf-destroy:
	cd terraform && terraform destroy

status:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl get pods -A

argocd-password:
	@KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

argocd-ui:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n argocd port-forward svc/argocd-server 8080:80

minio-ui:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n platform port-forward svc/minio-console 9001:9001

infra-init:
	cd infra/openstack && terraform init

infra-apply:
	cd infra/openstack && terraform apply

infra-destroy:
	cd infra/openstack && terraform destroy

k3s-remote:
	cd ansible && ansible-playbook -i inventory.openstack.ini playbooks/k3s-install.yml

data:
	python3 -m ml.src.generate_data --out ml/data/train.csv

train: data
	python3 -m ml.src.train --data ml/data/train.csv --out ml/models

test:
	python3 -m pytest -q

deploy-app:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl apply -f gitops/apps/churn-api.yaml

api-forward:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n mlops port-forward svc/churn-api 8000:80

api-test:
	curl -s localhost:8000/predict -H 'Content-Type: application/json' -d '{"tenure":2,"monthly_charges":95,"total_charges":190,"support_tickets":3,"senior_citizen":1,"contract":"Month-to-month","internet_service":"Fiber optic","payment_method":"Electronic check","tech_support":"No"}'; echo

grafana-ui:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n monitoring port-forward svc/kps-grafana 3000:80

prometheus-ui:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n monitoring port-forward svc/kps-prometheus 9090:9090

alertmanager-ui:
	KUBECONFIG=$(KUBECONFIG_FILE) kubectl -n monitoring port-forward svc/kps-alertmanager 9093:9093

traffic:
	python3 chaos/traffic.py --rps 5 --duration 180

traffic-drift:
	python3 chaos/traffic.py --rps 5 --duration 180 --drift
