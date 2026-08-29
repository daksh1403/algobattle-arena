# ============================================================================
# Algobattle — AWS main composition
# ----------------------------------------------------------------------------
# Single-VPC, single-AZ (configurable), single ALB, two EC2s, one RDS.
# All other services (Judge0, API, workers) run as Docker Compose on the EC2s.
# ============================================================================

locals {
  # Common tags (merged with default_tags from provider)
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ----------------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------------
module "network" {
  source = "./modules/network"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  az_count           = var.vpc_az_count
  enable_nat_gateway = var.enable_nat_gateway
}

# ----------------------------------------------------------------------------
# Database (RDS postgres)
# ----------------------------------------------------------------------------
module "database" {
  source = "./modules/database"

  project_name  = var.project_name
  environment   = var.environment
  vpc_id        = module.network.vpc_id
  vpc_cidr      = var.vpc_cidr
  subnet_ids    = module.network.private_subnet_ids
  db_subnet_ids = module.network.database_subnet_ids

  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  db_name               = var.db_name
  db_username           = var.db_username
  multi_az              = var.db_multi_az
}

# ----------------------------------------------------------------------------
# Compute — API + worker EC2
# ----------------------------------------------------------------------------
module "compute" {
  source = "./modules/compute"

  project_name      = var.project_name
  environment       = var.environment
  instance_type     = var.api_instance_type
  volume_size       = var.api_volume_size
  volume_type       = var.api_volume_type
  vpc_id            = module.network.vpc_id
  subnet_ids        = module.network.public_subnet_ids
  ssh_key_name      = var.ssh_key_name
  ssh_allowed_cidrs = var.ssh_allowed_cidrs

  image_api      = var.image_api
  image_judge    = var.image_judge
  image_frontend = var.image_frontend

  rds_endpoint  = module.database.endpoint
  rds_port      = module.database.port
  db_secret_arn = module.database.secret_arn

  github_org = var.github_org

  # Allow this EC2 to pull from RDS via the DB SG
  rds_security_group_id = module.database.security_group_id
}

# ----------------------------------------------------------------------------
# Judge0 — dedicated isolated EC2
# ----------------------------------------------------------------------------
module "judge0" {
  source = "./modules/judge0"

  project_name      = var.project_name
  environment       = var.environment
  instance_type     = var.judge0_instance_type
  volume_size       = var.judge0_volume_size
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  ssh_key_name      = var.ssh_key_name
  ssh_allowed_cidrs = var.ssh_allowed_cidrs

  # Judge0 needs to call back to the API for results
  api_security_group_id = module.compute.api_security_group_id
}

# ----------------------------------------------------------------------------
# ALB
# ----------------------------------------------------------------------------
resource "aws_lb" "main" {
  name               = "${var.project_name}-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.network.public_subnet_ids

  enable_deletion_protection = var.environment == "prod"

  tags = local.common_tags
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-alb"
  description = "ALB ingress"
  vpc_id      = module.network.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# ACM cert (only if a domain is provided)
resource "aws_acm_certificate" "main" {
  count             = var.domain_name != "" ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = local.common_tags
}

# ALB target group → API EC2
resource "aws_lb_target_group" "api" {
  name        = "${var.project_name}-${var.environment}-api"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = module.network.vpc_id
  target_type = "instance"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    timeout             = 5
    interval            = 15
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = local.common_tags
}

resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = module.compute.api_instance_id
  port             = 80
}

# ALB listener — HTTP (redirect to HTTPS) + HTTPS (forward to API)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.acm_certificate_arn != "" || var.domain_name != "" ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.acm_certificate_arn != "" || var.domain_name != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    target_group_arn = var.acm_certificate_arn != "" || var.domain_name != "" ? null : aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "https" {
  count             = (var.acm_certificate_arn != "" || var.domain_name != "") ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn != "" ? var.acm_certificate_arn : try(aws_acm_certificate.main[0].arn, "")

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}