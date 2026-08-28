# Terraform: EKS reference deployment

A reference AWS deployment for the backend/worker: VPC (2 AZs, NAT gateway),
an EKS cluster with one managed node group, an RDS Postgres instance, an
ElastiCache Redis node, and an S3 bucket for repository/artifact storage. It
is a **reference**, not a one-click production setup -- read
[docs/deployment.md](../../docs/deployment.md) and the cost warning below
before running `apply`.

This configuration has been run through `terraform fmt -check`,
`terraform init -backend=false`, and `terraform validate` (all passing). It
has **not** been `apply`'d -- no AWS account was provisioned as part of this
project, deliberately, per the program's local-first/no-paid-services
constraint during development.

## Cost warning

Every resource here is billed. Approximate on-demand US-East-1 pricing at
time of writing, for the tfvars.example defaults:

| Resource | Approx. cost |
|---|---|
| EKS control plane | ~$73/mo |
| 2x t3.large nodes (on-demand) | ~$150/mo |
| NAT gateway (single) | ~$33/mo + data processing |
| db.t4g.medium RDS (single-AZ) | ~$60/mo |
| cache.t4g.small ElastiCache | ~$25/mo |
| S3, Secrets Manager, EBS | a few dollars/mo at this scale |

**Total: roughly $350-400/month** for the reference sizing, before data
transfer. Reduce `node_group_desired_size`, use `db.t4g.micro`, and/or
schedule the cluster down outside business hours to cut this significantly
for a demo/staging use case. Nothing here is eligible for further discount
without a Savings Plan or Reserved Instances.

## Usage

```bash
cd terraform/eks
cp terraform.tfvars.example terraform.tfvars   # edit as needed
terraform init                                  # configure a real backend first, see versions.tf
terraform plan
terraform apply
```

## Destroy / cleanup

```bash
terraform destroy
```

Notes:
- `skip_final_snapshot = true` on the RDS instance means `destroy` does **not**
  leave a final snapshot behind. Set it to `false` (and set
  `final_snapshot_identifier`) before destroying anything containing real data.
- The S3 bucket has no `force_destroy`; if it contains objects, `destroy` will
  fail until you empty it (`aws s3 rm s3://<bucket> --recursive`) -- this is
  intentional, to avoid silently deleting ingested-repository data.
- Confirm no orphaned EBS volumes or load balancers remain after `destroy`
  finishes (the AWS Load Balancer Controller, if installed separately from
  this module, can leave an ALB/NLB behind that Terraform doesn't know about).

## What this does not include

- No AWS Load Balancer Controller, cert-manager, or external-dns Helm
  releases -- install those separately (or extend this module) before
  applying `k8s/06-ingress.yaml`.
- No CI/CD pipeline wiring (image push to a registry, `kubectl apply`
  automation) -- see `docs/deployment.md`.
- No multi-AZ RDS/ElastiCache HA -- single-AZ is the reference default to
  control cost; flip to Multi-AZ for a real production SLA.
