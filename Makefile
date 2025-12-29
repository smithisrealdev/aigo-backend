# ===========================================
# AiGo Backend - Makefile
# ===========================================
# Usage: make <target>
# Run 'make help' for available commands
# ===========================================

.PHONY: help install dev test lint format clean docker-build docker-up docker-down docker-logs migrate

# Default shell
SHELL := /bin/bash

# Project variables
PROJECT_NAME := aigo-backend
PYTHON := python3
POETRY := poetry

# Docker compose files
COMPOSE_BASE := docker-compose.yaml
COMPOSE_DEV := docker-compose.dev.yaml
COMPOSE_PROD := docker-compose.prod.yaml
DOCKER_COMPOSE_DEV := docker-compose -f $(COMPOSE_BASE) -f $(COMPOSE_DEV)
DOCKER_COMPOSE_PROD := docker-compose -f $(COMPOSE_BASE) -f $(COMPOSE_PROD)

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# ===========================================
# Help
# ===========================================
help: ## Show this help message
	@echo ""
	@echo "$(CYAN)AiGo Backend - Available Commands$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<target>$(RESET)\n\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(YELLOW)%s$(RESET)\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""

##@ Development Setup

install: ## Install dependencies with Poetry
	@echo "$(CYAN)Installing dependencies...$(RESET)"
	$(POETRY) install
	@echo "$(GREEN)✅ Dependencies installed$(RESET)"

setup: install ## Complete project setup
	@echo "$(CYAN)Setting up project...$(RESET)"
	cp -n .env.example .env 2>/dev/null || true
	$(POETRY) run pre-commit install 2>/dev/null || true
	@echo "$(GREEN)✅ Project setup complete$(RESET)"

update: ## Update dependencies
	@echo "$(CYAN)Updating dependencies...$(RESET)"
	$(POETRY) update
	@echo "$(GREEN)✅ Dependencies updated$(RESET)"

##@ Running Application

dev: ## Run development server with hot reload
	@echo "$(CYAN)Starting development server...$(RESET)"
	$(POETRY) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run: ## Run production server locally
	@echo "$(CYAN)Starting production server...$(RESET)"
	$(POETRY) run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

##@ Testing

test: ## Run all tests
	@echo "$(CYAN)Running tests...$(RESET)"
	$(POETRY) run pytest -v

test-cov: ## Run tests with coverage
	@echo "$(CYAN)Running tests with coverage...$(RESET)"
	$(POETRY) run pytest --cov=app --cov-report=html --cov-report=term-missing

test-watch: ## Run tests in watch mode
	@echo "$(CYAN)Running tests in watch mode...$(RESET)"
	$(POETRY) run pytest-watch

##@ Code Quality

lint: ## Run linters (ruff, mypy)
	@echo "$(CYAN)Running linters...$(RESET)"
	$(POETRY) run ruff check app tests
	$(POETRY) run mypy app
	@echo "$(GREEN)✅ Linting complete$(RESET)"

format: ## Format code with ruff
	@echo "$(CYAN)Formatting code...$(RESET)"
	$(POETRY) run ruff format app tests
	$(POETRY) run ruff check --fix app tests
	@echo "$(GREEN)✅ Formatting complete$(RESET)"

check: lint test ## Run all checks (lint + test)
	@echo "$(GREEN)✅ All checks passed$(RESET)"

##@ Database

migrate: ## Run database migrations
	@echo "$(CYAN)Running migrations...$(RESET)"
	$(POETRY) run alembic upgrade head
	@echo "$(GREEN)✅ Migrations complete$(RESET)"

migrate-new: ## Create new migration (usage: make migrate-new msg="migration message")
	@echo "$(CYAN)Creating new migration...$(RESET)"
	$(POETRY) run alembic revision --autogenerate -m "$(msg)"
	@echo "$(GREEN)✅ Migration created$(RESET)"

migrate-down: ## Rollback last migration
	@echo "$(CYAN)Rolling back migration...$(RESET)"
	$(POETRY) run alembic downgrade -1
	@echo "$(GREEN)✅ Migration rolled back$(RESET)"

migrate-reset: ## Reset all migrations
	@echo "$(RED)⚠️  Resetting all migrations...$(RESET)"
	$(POETRY) run alembic downgrade base
	@echo "$(GREEN)✅ Migrations reset$(RESET)"

##@ Docker Development

docker-build: ## Build Docker images
	@echo "$(CYAN)Building Docker images...$(RESET)"
	$(DOCKER_COMPOSE_DEV) build
	@echo "$(GREEN)✅ Docker images built$(RESET)"

docker-up: ## Start development containers
	@echo "$(CYAN)Starting development containers...$(RESET)"
	$(DOCKER_COMPOSE_DEV) up -d
	@echo "$(GREEN)✅ Containers started$(RESET)"
	@echo "$(CYAN)API: http://localhost:8000$(RESET)"
	@echo "$(CYAN)Docs: http://localhost:8000/docs$(RESET)"

docker-up-full: ## Start all containers including tools
	@echo "$(CYAN)Starting all containers...$(RESET)"
	$(DOCKER_COMPOSE_DEV) --profile tools --profile celery up -d
	@echo "$(GREEN)✅ All containers started$(RESET)"
	@echo "$(CYAN)API: http://localhost:8000$(RESET)"
	@echo "$(CYAN)pgAdmin: http://localhost:5050$(RESET)"
	@echo "$(CYAN)Redis Commander: http://localhost:8081$(RESET)"
	@echo "$(CYAN)MailHog: http://localhost:8025$(RESET)"

docker-down: ## Stop all containers
	@echo "$(CYAN)Stopping containers...$(RESET)"
	$(DOCKER_COMPOSE_DEV) --profile tools --profile celery --profile monitoring down
	@echo "$(GREEN)✅ Containers stopped$(RESET)"

docker-restart: docker-down docker-up ## Restart containers

docker-logs: ## View container logs
	$(DOCKER_COMPOSE_DEV) logs -f

docker-logs-api: ## View API container logs
	$(DOCKER_COMPOSE_DEV) logs -f api

docker-shell: ## Open shell in API container
	$(DOCKER_COMPOSE_DEV) exec api /bin/bash

docker-clean: ## Remove all containers and volumes
	@echo "$(RED)⚠️  Removing all containers and volumes...$(RESET)"
	$(DOCKER_COMPOSE_DEV) --profile tools --profile celery --profile monitoring down -v --remove-orphans
	docker system prune -f
	@echo "$(GREEN)✅ Cleanup complete$(RESET)"

##@ Docker Production

docker-prod-build: ## Build production Docker images
	@echo "$(CYAN)Building production images...$(RESET)"
	$(DOCKER_COMPOSE_PROD) build
	@echo "$(GREEN)✅ Production images built$(RESET)"

docker-prod-up: ## Start production containers
	@echo "$(CYAN)Starting production containers...$(RESET)"
	$(DOCKER_COMPOSE_PROD) up -d
	@echo "$(GREEN)✅ Production containers started$(RESET)"

docker-prod-down: ## Stop production containers
	@echo "$(CYAN)Stopping production containers...$(RESET)"
	$(DOCKER_COMPOSE_PROD) down
	@echo "$(GREEN)✅ Production containers stopped$(RESET)"

##@ Database Docker

db-shell: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE_DEV) exec postgres psql -U aigo -d aigo_db

db-backup: ## Backup database
	@echo "$(CYAN)Backing up database...$(RESET)"
	@mkdir -p backups
	$(DOCKER_COMPOSE_DEV) exec -T postgres pg_dump -U aigo aigo_db > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Backup created$(RESET)"

db-restore: ## Restore database (usage: make db-restore file=backup.sql)
	@echo "$(CYAN)Restoring database...$(RESET)"
	$(DOCKER_COMPOSE_DEV) exec -T postgres psql -U aigo -d aigo_db < $(file)
	@echo "$(GREEN)✅ Database restored$(RESET)"

redis-shell: ## Open Redis CLI
	$(DOCKER_COMPOSE_DEV) exec redis redis-cli

##@ Utilities

clean: ## Clean cache and build files
	@echo "$(CYAN)Cleaning cache files...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Cache cleaned$(RESET)"

env-check: ## Check environment setup
	@echo "$(CYAN)Checking environment...$(RESET)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Poetry: $$($(POETRY) --version)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker-compose --version)"
	@echo "$(GREEN)✅ Environment check complete$(RESET)"

version: ## Show project version
	@$(POETRY) version

# ===========================================
# Default target
# ===========================================
.DEFAULT_GOAL := help
