resource "aws_s3_bucket" "repositories" {
  bucket = "${local.cluster_name}-repositories"
}

resource "aws_s3_bucket_public_access_block" "repositories" {
  bucket                  = aws_s3_bucket.repositories.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "repositories" {
  bucket = aws_s3_bucket.repositories.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "repositories" {
  bucket = aws_s3_bucket.repositories.id
  rule {
    id     = "expire-old-artifacts"
    status = "Enabled"
    expiration {
      days = 90
    }
  }
}

# Least-privilege IAM policy for the backend's S3 access (scoped to this one
# bucket only), attached to the pod via a Pod Identity association below --
# no static access keys are provisioned or required.
data "aws_iam_policy_document" "s3_access" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.repositories.arn,
      "${aws_s3_bucket.repositories.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "s3_access" {
  name   = "${local.cluster_name}-s3-access"
  policy = data.aws_iam_policy_document.s3_access.json
}

resource "aws_iam_role" "backend_pod" {
  name = "${local.cluster_name}-backend-pod"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "backend_pod_s3" {
  role       = aws_iam_role.backend_pod.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_eks_pod_identity_association" "backend" {
  cluster_name    = module.eks.cluster_name
  namespace       = "masea"
  service_account = "masea-backend"
  role_arn        = aws_iam_role.backend_pod.arn
}
