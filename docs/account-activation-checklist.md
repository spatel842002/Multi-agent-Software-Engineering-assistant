# Account activation checklist

Everything in this project runs locally, for free, with no account or paid
API key — see [Quickstart](../README.md#quickstart). This checklist is only
needed if you want to deploy the Kubernetes/Terraform reference to real
cloud infrastructure. Nothing on this list was created for this project;
all of it is deferred, as intended.

| # | Feature | Provider | Required? | Free tier / alternative | Resource to create | Env var(s) | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Cloud infrastructure | AWS | Required for the Terraform/EKS path only | None (paid) — see [cost warning](../terraform/eks/README.md#cost-warning) | An AWS account + an IAM user/role with permissions to create VPC/EKS/RDS/ElastiCache/S3/IAM/Secrets Manager resources | AWS credentials configured for the Terraform AWS provider (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or an assumed role) | Least-privilege: scope the IAM policy to exactly the resource types in `terraform/eks/*.tf`, not `AdministratorAccess` |
| 2 | Terraform remote state | AWS (S3 + DynamoDB) or Terraform Cloud | Recommended before any real `apply` | S3/DynamoDB free tier likely covers state storage; Terraform Cloud has a free tier | An S3 bucket + DynamoDB lock table (or a Terraform Cloud workspace) | Uncomment and fill in the `backend "s3" {}` block in `terraform/eks/versions.tf` | Without this, state is only ever local — do not use local state for a shared/production deployment |
| 3 | Container registry | GitHub Container Registry (GHCR), free for public images | Required to deploy built images | GHCR free for public repos | Enable GHCR for the repo (Settings → Packages), or create an ECR repository instead | Update `image:` in `k8s/03-backend.yaml`, `k8s/04-worker.yaml`, `k8s/05-frontend.yaml` | `docker push` requires `docker login ghcr.io` with a PAT that has `write:packages` |
| 4 | DNS + TLS | Any DNS registrar + Let's Encrypt (via cert-manager) | Required for a real public URL | Let's Encrypt is free; DNS registration cost varies by registrar | A domain, an A/CNAME record to the ingress load balancer, a cert-manager `ClusterIssuer` | Replace `masea.example.com` in `k8s/06-ingress.yaml` | cert-manager itself is not installed by this project's Terraform/k8s — install it separately (its own Helm chart) |
| 5 | Ingress controller | `ingress-nginx` (or any Ingress controller) | Required for `k8s/06-ingress.yaml` to do anything | Free, self-hosted Helm chart | Install `ingress-nginx` into the cluster | `ingressClassName: nginx` in `k8s/06-ingress.yaml` must match what you install | Not provisioned by `terraform/eks/` |
| 6 | Dense vector store in production | Qdrant | Required (or self-host) | Self-host Qdrant in-cluster (free) or Qdrant Cloud's free tier | A Qdrant deployment reachable from the cluster, or a Qdrant Cloud cluster | `QDRANT_URL`, `QDRANT_API_KEY` in `k8s/01-configmap.yaml`/`02-secret.yaml` | Not provisioned by this Terraform module — self-host it in-cluster (a StatefulSet is the natural addition) or point at a managed instance |
| 7 | LLM/embedding provider in production | Ollama (self-hosted) or any OpenAI-API-compatible hosted provider | Required (or self-host) | Self-hosted Ollama is free but needs a GPU-backed node for reasonable latency at scale | A reachable Ollama-compatible endpoint | `OLLAMA_BASE_URL` (and swap `services/llm/providers.py`'s provider if using a non-Ollama API) | The `LLM_PROVIDER` setting today only supports `ollama`/`fake` — adding a hosted provider is a real, not-yet-done extension (a new `ChatProvider` implementation behind the existing `Protocol`) |
| 8 | Secret management | AWS Secrets Manager (RDS password only, provisioned already) or your own choice | The RDS password is already handled | N/A | Already created by `terraform/eks/rds.tf`'s `random_password`/`aws_secretsmanager_secret` | Retrieve with `aws secretsmanager get-secret-value --secret-id <output.db_password_secret_arn>` | `JWT_SECRET_KEY` and other app secrets still need to be generated and placed into `k8s/02-secret.yaml` manually — see step below |

## Verification commands (after completing the above)

```bash
kubectl -n masea get pods                       # everything Running
curl https://<your-domain>/api/v1/health         # {"status": "ok"}
curl https://<your-domain>/api/v1/ready          # {"ready": true, ...}
```

## Cost risk and cleanup

See [terraform/eks/README.md](../terraform/eks/README.md) for the full cost
table and `terraform destroy` instructions. Nothing above was provisioned
as part of building this project — no AWS account, domain, or container
registry was created or charged.
