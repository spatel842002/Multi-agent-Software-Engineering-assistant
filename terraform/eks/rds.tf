resource "random_password" "db" {
  length  = 32
  special = false # avoid characters that require URL-encoding in DATABASE_URL
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${local.cluster_name}-db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db.result
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.cluster_name}-db"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "db" {
  name_prefix = "${local.cluster_name}-db-"
  description = "Allow Postgres access from inside the VPC only."
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Postgres from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.cluster_name}-db"
  engine         = "postgres"
  engine_version = "17"

  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage_gb
  storage_type           = "gp3"
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  publicly_accessible     = false
  backup_retention_period = 7
  deletion_protection     = false # set true before running this against a real production database
  skip_final_snapshot     = true  # set false (and set final_snapshot_identifier) for production
  apply_immediately       = false
}
