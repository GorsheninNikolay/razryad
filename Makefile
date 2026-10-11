# РАЗРЯД Platform - Makefile
# Quick commands for development and deployment

.PHONY: help venv dev demo build test migrate seed clean docker-build docker-up docker-up-postgres docker-down setup

# Default target
help:
	@echo "РАЗРЯД Platform - Available commands:"
	@echo ""
	@echo "  make dev          - Run backend in dev mode (SQLite, auto-reload)"
	@echo "  make demo         - Migrate + seed + run the whole stack on :8000"
	@echo "  make build        - Build frontend for production"
	@echo "  make test         - Run tests"
	@echo "  make migrate      - Run database migrations"
	@echo "  make seed         - Seed database with test data"
	@echo "  make clean        - Clean build artifacts and cache"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start Docker Compose stack"
	@echo "  make docker-down  - Stop Docker Compose stack"
	@echo ""

# Ensure the backend virtualenv exists, so `make demo` works on a clean machine
venv:
	@if [ ! -d backend/venv ]; then \
		echo "🔧 Creating backend virtualenv (first run)..."; \
		cd backend && python3 -m venv venv && . venv/bin/activate && pip install -q -r requirements.txt; \
		echo "✓ Virtualenv ready"; \
	fi

# Development mode: backend only with auto-reload
dev: venv
	@echo "🚀 Starting backend in dev mode..."
	cd backend && . venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Demo mode: migrate, seed demo data, run the full stack on one port
demo: venv migrate seed
	@echo "🎬 Starting РАЗРЯД demo at http://localhost:8000 ..."
	cd backend && . venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Build frontend
build:
	@echo "🏗️  Building frontend..."
	cd frontend && npm install && npm run build
	@echo "✓ Frontend built to frontend/dist"

# Run tests
test:
	@echo "🧪 Running tests..."
	cd backend && . venv/bin/activate && pytest

# Database migrations
migrate:
	@echo "📊 Running database migrations..."
	cd backend && . venv/bin/activate && alembic upgrade head
	@echo "✓ Database schema up to date"

# Seed database with test data
seed:
	@echo "🌱 Seeding database..."
	cd backend && . venv/bin/activate && python seed/seed.py
	@echo "✓ Database seeded"

# Clean build artifacts. NOTE: the shared dev database is deliberately NOT removed —
# deleting it while teammates are working corrupts their runs. Use `make reset-db`.
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache
	rm -rf frontend/dist
	rm -rf frontend/node_modules
	@echo "✓ Cleaned (база backend/razryad.db сохранена)"

# Explicitly recreate the shared database. Run only when nobody else is working.
reset-db:
	@echo "⚠️  Удаляю общую базу backend/razryad.db и пересоздаю схему..."
	rm -f backend/razryad.db
	$(MAKE) migrate
	$(MAKE) seed
	@echo "✓ База пересоздана"

# Docker build
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t razryad:latest .
	@echo "✓ Docker image built"

# Docker Compose up (SQLite by default)
docker-up:
	@echo "🐳 Starting Docker Compose stack..."
	docker compose up -d
	@echo "✓ Stack running at http://localhost:8000"

# Docker Compose up with PostgreSQL
docker-up-postgres:
	@echo "🐳 Starting Docker Compose stack with PostgreSQL..."
	docker compose --profile postgres up -d
	@echo "✓ Stack running at http://localhost:8000"

# Docker Compose down
docker-down:
	@echo "🐳 Stopping Docker Compose stack..."
	docker compose down
	@echo "✓ Stack stopped"

# Setup development environment
setup:
	@echo "🔧 Setting up development environment..."
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Backend environment ready"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and configure"
	@echo "  2. Run 'make migrate' to create database schema"
	@echo "  3. Run 'make dev' to start development server"
