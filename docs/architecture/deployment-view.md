# Deployment view

## Local (Docker Compose) — verified, this is what was actually run

```mermaid
flowchart TB
    subgraph host["Docker host (one machine)"]
        subgraph compose["docker-compose.yml network: masea_default"]
            fe["frontend<br/>(nginx, port 80)"]
            be["backend<br/>(uvicorn, port 8000)"]
            wk["worker<br/>(celery)"]
            pg[("postgres:17")]
            rd[("redis:8")]
            qd[("qdrant:v1.12.4")]
            ol[("ollama:0.6.2")]
            mi[("minio")]
            ml[("mlflow<br/>(python:3.11-slim + pip install)")]
            pr[("prometheus:v3.1.0")]
            gr[("grafana:11.4.0")]
        end
    end
    browser["Your browser"] -->|":5173 (mapped)"| fe
    fe -->|"/api/* proxy_pass"| be
    be --> pg
    be --> rd
    be --> qd
    be --> ol
    be --> mi
    wk --> pg
    wk --> qd
    wk --> rd
    pr -->|scrape /metrics| be
    gr --> pr
    ml -.->|evals/run_evals.py optionally points here| be
```

Every host port is overridable (`.env` at the repo root, see
`docs/environment-variables.md`) to avoid conflicts with anything else
running on the same machine — this mattered in practice during development
(the dev machine had another, unrelated project's Compose stack running
concurrently on several default ports).

## Production reference (Kubernetes on EKS) — infra-validated, not live-deployed

```mermaid
flowchart TB
    subgraph aws["AWS (terraform/eks/)"]
        subgraph vpc["VPC (2 AZs)"]
            subgraph eks["EKS cluster"]
                subgraph ns["namespace: masea"]
                    fe2["Deployment: masea-frontend<br/>(2 replicas)"]
                    be2["Deployment: masea-backend<br/>(2 replicas, HPA 2-6)"]
                    wk2["Deployment: masea-worker<br/>(2 replicas)"]
                    svcfe["Service: masea-frontend"]
                    svcbe["Service: masea-backend"]
                    ing["Ingress<br/>(nginx-ingress + cert-manager, not provisioned here)"]
                end
            end
            rds[("RDS Postgres 17<br/>single-AZ, private subnet")]
            cache[("ElastiCache Redis 7.1<br/>private subnet")]
        end
        s3[("S3 bucket<br/>masea-*-repositories")]
        sm["Secrets Manager<br/>(generated RDS password)"]
        pid["EKS Pod Identity<br/>-> IAM role -> S3 access"]
    end
    ext["External Ollama-compatible<br/>endpoint (not provisioned)"]

    Internet -->|HTTPS| ing --> svcfe --> fe2
    ing --> svcbe --> be2
    be2 --> rds
    be2 --> cache
    be2 --> s3
    be2 -.pod identity, no static keys.-> pid
    be2 -.-> ext
    wk2 --> rds
    wk2 --> cache
```

**What Terraform provisions**: VPC, EKS cluster + one managed node group,
RDS Postgres, ElastiCache Redis, an S3 bucket, and least-privilege IAM (Pod
Identity, no static AWS access keys). **What it does not provision**:
Qdrant, Ollama/an LLM endpoint, the nginx ingress controller, cert-manager,
or DNS — see `docs/account-activation-checklist.md` for exactly what's
left as an account/DNS/manual step, and `terraform/eks/README.md` for the
cost warning before running `apply`.

**Verification status**: `terraform fmt`/`init -backend=false`/`validate`
all pass against real Postgres-backed module resolution; `k8s/` manifests
are YAML-valid (`yaml.safe_load`) and, in CI, schema-validated with
`kubeconform`. Neither has been run against a live cluster or a real AWS
account in this environment — no cluster was created, matching the
program's local-first, no-paid-services-during-development constraint.
