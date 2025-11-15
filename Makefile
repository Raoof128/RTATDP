# Makefile for AI Threat Detection System
# Common development and deployment tasks

.PHONY: help install test lint format clean docker-build docker-up docker-down k8s-deploy

help:
	@echo "AI Threat Detection System - Make Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Clean build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start docker-compose stack"
	@echo "  make docker-down   - Stop docker-compose stack"
	@echo "  make docker-logs   - View docker-compose logs"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make k8s-deploy    - Deploy to Kubernetes"
	@echo "  make k8s-delete    - Delete from Kubernetes"
	@echo "  make k8s-status    - Check deployment status"
	@echo ""
	@echo "Models:"
	@echo "  make train         - Train ML models"
	@echo "  make serve         - Start inference server"

# Development
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .

install-dev:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-asyncio black flake8 mypy bandit
	pip install -e .

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-fast:
	pytest tests/ -v --tb=short

lint:
	@echo "Running flake8..."
	flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503
	@echo "Running mypy..."
	mypy src/ --ignore-missing-imports
	@echo "Running bandit..."
	bandit -r src/ -ll

format:
	@echo "Formatting with black..."
	black src/ tests/
	@echo "Sorting imports..."
	isort src/ tests/

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info
	rm -rf htmlcov/ .coverage .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Docker
docker-build:
	docker build -t threat-detector:latest .

docker-build-no-cache:
	docker build --no-cache -t threat-detector:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

docker-clean:
	docker-compose down -v
	docker system prune -f

# Kubernetes
k8s-deploy:
	kubectl create namespace security || true
	kubectl apply -f deployment/kubernetes/

k8s-delete:
	kubectl delete -f deployment/kubernetes/

k8s-status:
	kubectl get pods -n security
	kubectl get services -n security
	kubectl get hpa -n security

k8s-logs:
	kubectl logs -n security -l app=threat-detector --tail=100 -f

# Models
train:
	jupyter nbconvert --to notebook --execute notebooks/01_model_training_demo.ipynb

serve:
	uvicorn src.inference_server.api:app --host 0.0.0.0 --port 8000 --reload

serve-prod:
	uvicorn src.inference_server.api:app --host 0.0.0.0 --port 8000 --workers 4

# Data pipeline
kafka-topics:
	docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

kafka-create-topics:
	docker-compose exec kafka kafka-topics --create --bootstrap-server localhost:9092 --topic security.events.network --partitions 10 --replication-factor 1
	docker-compose exec kafka kafka-topics --create --bootstrap-server localhost:9092 --topic security.events.endpoint --partitions 10 --replication-factor 1
	docker-compose exec kafka kafka-topics --create --bootstrap-server localhost:9092 --topic security.events.application --partitions 10 --replication-factor 1

# Monitoring
prometheus:
	open http://localhost:9090

grafana:
	open http://localhost:3000

# Security
security-scan:
	safety check
	bandit -r src/ -ll

# CI/CD
ci: lint test security-scan
	@echo "CI checks passed!"

# Setup
setup: install-dev docker-up kafka-create-topics
	@echo "Development environment ready!"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000"
