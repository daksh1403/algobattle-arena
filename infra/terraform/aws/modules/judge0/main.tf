# ============================================================================
# Judge0 module — dedicated EC2 (t3.large) running the Judge0 cluster
# ----------------------------------------------------------------------------
# Isolated on its own subnet / SG. Only the API EC2 can reach it on :2358.
# ============================================================================

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_iam_role" "main" {
  name = "${var.project_name}-${var.environment}-judge0"

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

resource "aws_iam_instance_profile" "main" {
  name = "${var.project_name}-${var.environment}-judge0"
  role = aws_iam_role.main.name
}

# Security group — only port 2358 from the API SG + SSH
resource "aws_security_group" "main" {
  name        = "${var.project_name}-${var.environment}-judge0"
  description = "Judge0 EC2"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Judge0 API from app"
    from_port       = 2358
    to_port         = 2358
    protocol        = "tcp"
    security_groups = [var.api_security_group_id]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-judge0-sg"
  }
}

resource "aws_instance" "main" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.main.id]
  iam_instance_profile   = aws_iam_instance_profile.main.name
  key_name               = var.ssh_key_name
  ebs_optimized          = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.volume_size
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "${var.project_name}-${var.environment}-judge0-root"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  user_data = templatefile("${path.module}/userdata.sh.tftpl", {
    project_name = var.project_name
    environment  = var.environment
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-judge0"
    Role = "judge0"
  }
}

resource "aws_eip" "main" {
  instance = aws_instance.main.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-${var.environment}-judge0-eip"
  }
}