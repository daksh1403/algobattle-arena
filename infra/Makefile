# ============================================================================
# Algobattle — Makefile
# ============================================================================
# Convenience entry-points. Run `make help` for a list of targets.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE      := docker compose
COMPOSE_DEV  := docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD := docker compose -f docker-compose.yml
JUDGE0_COMPOSE := docker compose -f judge0/docker-compose.judge0.yml --project-name algobattle-judge0

IMAGE_API      ?= algobattle-api:latest
IMAGE_JUDGE    ?= algobattle-judge:latest
IMAGE_FRONTEND ?= algobattle-frontend:latest
REGISTRY       ?= ghcr.io/your-org

# Subdir containing the backend code
BACKEND_DIR  := ../backend
FRONTEND_DIR := ../frontend
JUDGE_DIR    := ../judge

# ----------------------------------------------------------------------------
# Help
# ----------------------------------------------------------------------------
help:                           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------
# Local dev
# ----------------------------------------------------------------------------
dev:                            ## Start full dev stack (hot reload, exposed DB)
	@test -f .env || cp .env.example .env
	$(COMPOSE_DEV) up --build

dev-up: dev

dev-down:                       ## Stop dev stack
	$(COMPOSE_DEV) down

dev-logs:                       ## Tail dev logs
	$(COMPOSE_DEV) logs -f --tail=200

logs:                           ## Tail production stack logs
	$(COMPOSE_PROD) logs -f --tail=200

# ----------------------------------------------------------------------------
# Production stack
# ----------------------------------------------------------------------------
prod:                           ## Start prod stack (no Judge0)
	@test -f .env || (echo ".env missing — copy from .env.example"; exit 1)
	$(COMPOSE_PROD) up -d --build

prod-down:                      ## Stop prod stack
	$(COMPOSE_PROD) down

prod-full: prod                 ## Start prod stack + Judge0 (isolated network)
	$(JUDGE0_COMPOSE) up -d

# ----------------------------------------------------------------------------
# Monitoring only
# ----------------------------------------------------------------------------
monitoring:                     ## Start monitoring stack only
	$(COMPOSE_PROD) up -d prometheus grafana loki promtail alertmanager node-exporter

# ----------------------------------------------------------------------------
# Build / push
# ----------------------------------------------------------------------------
build:                          ## Build all images locally
	docker build -t $(IMAGE_API)        ./api
	docker build -t $(IMAGE_JUDGE)      ./judge
	docker build -t $(IMAGE_FRONTEND)   $(FRONTEND_DIR) -f $(FRONTEND_DIR)/Dockerfile

build-api:
	docker build -t $(IMAGE_API)        ./api

build-judge:
	docker build -t $(IMAGE_JUDGE)      ./judge

push:                           ## Tag + push images to GHCR
	docker tag $(IMAGE_API)      $(REGISTRY)/algobattle-api:$${TAG:-latest}
	docker tag $(IMAGE_JUDGE)    $(REGISTRY)/algobattle-judge:$${TAG:-latest}
	docker tag $(IMAGE_FRONTEND) $(REGISTRY)/algobattle-frontend:$${TAG:-latest}
	docker push $(REGISTRY)/algobattle-api:$${TAG:-latest}
	docker push $(REGISTRY)/algobattle-judge:$${TAG:-latest}
	docker push $(REGISTRY)/algobattle-frontend:$${TAG:-latest}

# ----------------------------------------------------------------------------
# Scale
# ----------------------------------------------------------------------------
scale:                          ## Scale judge workers (N=10)
	@test -n "$(N)" || (echo "Usage: make scale N=10"; exit 1)
	$(COMPOSE_PROD) up -d --no-deps --scale judge-worker=$(N)

# ----------------------------------------------------------------------------
# Test / smoke / load
# ----------------------------------------------------------------------------
seed:                           ## Load sample problems into DB
	./scripts/seed-problems.py

test:                           ## Run all test suites
	cd $(BACKEND_DIR) && pytest -q
	cd $(FRONTEND_DIR) && npm test --silent
	cd $(JUDGE_DIR) && pytest -q

smoke:                          ## Run smoke test against running stack
	./scripts/smoke-test.sh

load:                           ## Run a basic load test (RPS=20, DURATION=30s)
	@RPS=$${RPS:-20}; DUR=$${DUR:-30s}; ./scripts/load-test.sh $$RPS $$DUR

# ----------------------------------------------------------------------------
# Deploy
# ----------------------------------------------------------------------------
deploy:                         ## Zero-downtime deploy to staging (over SSH)
	./scripts/deploy.sh

# ----------------------------------------------------------------------------
# Clean
# ----------------------------------------------------------------------------
clean:                          ## Remove containers + volumes
	$(COMPOSE_PROD) down -v --remove-orphans
	$(JUDGE0_COMPOSE) down -v --remove-orphans
	docker volume prune -f

clean-images:                   ## Remove local images
	docker rmi $(IMAGE_API) $(IMAGE_JUDGE) $(IMAGE_FRONTEND) 2>/dev/null || true

# ----------------------------------------------------------------------------
# Kubernetes
# ----------------------------------------------------------------------------
helm-lint:
	helm lint ./helm

helm-template:
	helm template algobattle ./helm --namespace algobattle

helm-install:
	helm upgrade --install algobattle ./helm --namespace algobattle --create-namespace

# ----------------------------------------------------------------------------
# Terraform
# ----------------------------------------------------------------------------
tf-init:
	cd terraform/aws && terraform init

tf-plan:
	cd terraform/aws && terraform plan -var-file=environments/dev.tfvars

tf-apply:
	cd terraform/aws && terraform apply -var-file=environments/dev.tfvars

# ----------------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------------
ps:                             ## List running services
	$(COMPOSE_PROD) ps

shell-api:                      ## Open shell in API container
	$(COMPOSE_PROD) exec api /bin/bash

shell-db:                       ## Open psql against the DB
	$(COMPOSE_PROD) exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

redis-cli:                      ## Open redis-cli
	$(COMPOSE_PROD) exec redis redis-cli -a $$REDIS_PASSWORD

.PHONY: help dev dev-up dev-down dev-logs logs prod prod-down prod-full monitoring build build-api build-judge push scale seed test smoke load deploy clean clean-images helm-lint helm-template helm-install tf-init tf-plan tf-apply ps shell-api shell-db redis-cli