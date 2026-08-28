# Deployment

See [docs/architecture/deployment-view.md](architecture/deployment-view.md)
for the diagrams this doc references.

## Local (verified, this is what was actually run and tested)

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5-coder:1.5b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec backend alembic upgrade head
```

That's the entire local deployment. See
[docs/local-development.md](local-development.md) for details and
[docs/environment-variables.md](environment-variables.md) for every
override.

## Production reference (Kubernetes on EKS)

**Verification status, stated plainly**: the Terraform module passes
`fmt`/`init -backend=false`/`validate`; the Kubernetes manifests pass
`kubeconform -strict` (10/10 resources valid, both in CI and verified
locally). Neither has been run against a live AWS account or Kubernetes
cluster — no cloud account was
provisioned for this project, deliberately, per its local-first
development constraint. Treat everything below as a reviewed, validated
starting point, not a deploy-and-forget button.

### 1. Provision infrastructure

```bash
cd terraform/eks
cp terraform.tfvars.example terraform.tfvars   # edit as needed
# Configure a real remote backend first -- see the commented block in versions.tf
terraform init
terraform plan
terraform apply
```

Read the [cost warning](../terraform/eks/README.md#cost-warning) first —
roughly $350-400/month for the reference sizing.

### 2. Point kubectl at the new cluster

```bash
aws eks update-kubeconfig --region <your-region> --name <cluster-name-from-terraform-output>
```

### 3. Install cluster add-ons this module does not provision

- An ingress controller (e.g. `ingress-nginx`) — `k8s/06-ingress.yaml`
  assumes `ingressClassName: nginx`.
- `cert-manager`, if using the `ClusterIssuer` referenced in
  `k8s/06-ingress.yaml`'s annotations — otherwise remove that annotation
  and manage TLS another way.

### 4. Build and push images

```bash
docker build -t <your-registry>/masea-backend:latest ./backend
docker build -t <your-registry>/masea-frontend:latest ./frontend
docker push <your-registry>/masea-backend:latest
docker push <your-registry>/masea-frontend:latest
```

Update the `image:` fields in `k8s/03-backend.yaml`, `k8s/04-worker.yaml`,
`k8s/05-frontend.yaml` to match (they default to a `ghcr.io/spatel842002/...`
placeholder).

### 5. Configure and apply Kubernetes manifests

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
cp k8s/02-secret.yaml.example k8s/02-secret.yaml   # fill in real values, never commit it
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/03-backend.yaml -f k8s/04-worker.yaml -f k8s/05-frontend.yaml -f k8s/06-ingress.yaml
```

`k8s/01-configmap.yaml`'s `QDRANT_URL`/`OLLAMA_BASE_URL` assume you've
separately deployed Qdrant and an Ollama-compatible endpoint reachable from
the cluster — neither is provisioned by this Terraform module. See
[docs/account-activation-checklist.md](account-activation-checklist.md).

### 6. Run migrations

```bash
kubectl -n masea run migrate --rm -it --restart=Never \
  --image=<your-registry>/masea-backend:latest \
  --env-from=configmap/masea-backend-config --env-from=secret/masea-backend-secrets \
  -- alembic upgrade head
```

### 7. Verify

```bash
kubectl -n masea get pods
kubectl -n masea logs deployment/masea-backend
curl https://<your-domain>/api/v1/ready
```

## Rolling back

```bash
kubectl -n masea rollout undo deployment/masea-backend
```

See [docs/runbook.md](runbook.md) for more.

## Destroying infrastructure

```bash
cd terraform/eks
terraform destroy
```

See the [destroy/cleanup notes](../terraform/eks/README.md#destroy--cleanup)
in the Terraform README — in particular, the S3 bucket must be emptied
manually first (intentional, to avoid silently deleting ingested-repository
data), and RDS's `skip_final_snapshot=true` default means no automatic
backup is left behind.
