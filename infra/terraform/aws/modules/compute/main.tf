# ============================================================================
# Compute module — API + worker EC2 (t3.medium)
# ----------------------------------------------------------------------------
# Runs the full Algobattle compose stack:
#   * Traefik (port 80/443)
#   * API (port 8000)
#   * Judge workers (RQ)
#   * Postgres + Redis (local; RDS is the managed instance)
#   * Prometheus + Grafana + Loki
#
# Judge0 lives on a separate EC2 (see ../judge0).
# ============================================================================

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# IAM role — used for SSM, Secrets Manager, CloudWatch, ECR pull
resource "aws_iam_role" "main" {
  name = "${var.project_name}-${var.environment}-compute"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.main.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cw" {
  role       = aws_iam_role.main.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "secrets" {
  name = "${var.project_name}-${var.environment}-secrets"
  role = aws_iam_role.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Resource = [var.db_secret_arn]
    }]
  })
}

resource "aws_iam_instance_profile" "main" {
  name = "${var.project_name}-${var.environment}-compute"
  role = aws_iam_role.main.name
}

# Security group — only 80/443 + SSH open
resource "aws_security_group" "api" {
  name        = "${var.project_name}-${var.environment}-api"
  description = "API EC2 — Traefik + SSH"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  ingress {
    description     = "Judge0 → API callback"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.judge0_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-api-sg"
  }
}

# EC2 instance
resource "aws_instance" "api" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.api.id]
  iam_instance_profile   = aws_iam_instance_profile.main.name
  key_name               = var.ssh_key_name
  ebs_optimized          = true

  root_block_device {
    volume_type           = var.volume_type
    volume_size           = var.volume_size
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "${var.project_name}-${var.environment}-api-root"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  user_data = templatefile("${path.module}/userdata.sh.tftpl", {
    environment    = var.environment
    project_name   = var.project_name
    image_api      = var.image_api
    image_judge    = var.image_judge
    image_frontend = var.image_frontend
    github_org     = var.github_org
    db_secret_arn  = var.db_secret_arn
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-api"
    Role = "api-worker"
  }
}

# Elastic IP (stable address)
resource "aws_eip" "api" {
  instance = aws_instance.api.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-${var.environment}-api-eip"
  }
}