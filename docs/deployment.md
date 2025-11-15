# Deployment Guide

This guide covers deploying the AI Threat Detection Pipeline in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Platforms](#cloud-platforms)
6. [Configuration](#configuration)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum (Development):**
- 4 CPU cores
- 8 GB RAM
- 20 GB disk space
- Docker 20.10+
- Docker Compose 2.0+

**Recommended (Production):**
- 16 CPU cores
- 64 GB RAM
- 500 GB SSD
- Kubernetes 1.28+
- Load balancer

### Software Dependencies

- Python 3.11 or higher
- Docker and Docker Compose
- kubectl (for Kubernetes)
- Helm 3.x (optional, for Helm deployment)
- Git

---

## Local Development

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd RTATDP

# Run automated setup
bash scripts/quick_start.sh

# Verify deployment
bash scripts/health_check.sh
```

### Manual Setup

```bash
# 1. Create environment file
cp .env.example .env
# Edit .env with your configuration

# 2. Start infrastructure
docker-compose up -d

# 3. Create Kafka topics
make kafka-create-topics

# 4. Install Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Run tests
make test

# 6. Start API server
make serve
```

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | N/A |
| Prometheus | http://localhost:9090 | N/A |
| Grafana | http://localhost:3000 | admin/admin |
| Kafka | localhost:9092 | N/A |
| Redis | localhost:6379 | N/A |

---

## Docker Deployment

### Building Images

```bash
# Build production image
docker build -t threat-detector:1.0.0 .

# Build with custom tag
docker build -t myregistry/threat-detector:latest .

# Push to registry
docker push myregistry/threat-detector:latest
```

### Docker Compose Production

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'
services:
  inference-server:
    image: threat-detector:1.0.0
    restart: always
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      - REDIS_URL=redis://redis:6379/0
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9093
    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

Start production stack:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (v1.28+)
- kubectl configured
- Ingress controller installed
- Persistent volume provisioner

### Step 1: Create Namespace

```bash
kubectl create namespace security
kubectl config set-context --current --namespace=security
```

### Step 2: Create ConfigMaps and Secrets

```bash
# ConfigMap
kubectl create configmap threat-detector-config \
  --from-literal=redis_url=redis://redis-service:6379/0 \
  --from-literal=kafka_bootstrap_servers=kafka-service:9092

# Secrets
kubectl create secret generic threat-detector-secrets \
  --from-literal=db_password=your-secure-password \
  --from-literal=splunk_hec_token=your-hec-token \
  --from-literal=thehive_api_key=your-api-key
```

### Step 3: Deploy Infrastructure

```bash
# Deploy Redis
kubectl apply -f deployment/kubernetes/redis-deployment.yaml

# Deploy Kafka (or use managed service)
kubectl apply -f deployment/kubernetes/kafka-deployment.yaml

# Deploy PostgreSQL
kubectl apply -f deployment/kubernetes/postgres-deployment.yaml
```

### Step 4: Deploy Application

```bash
# Deploy inference server
kubectl apply -f deployment/kubernetes/inference-deployment.yaml

# Verify deployment
kubectl get pods
kubectl get services
kubectl get hpa
```

### Step 5: Configure Ingress

```bash
# Apply ingress
kubectl apply -f deployment/kubernetes/ingress.yaml

# Get ingress IP
kubectl get ingress
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment threat-detector-inference --replicas=5

# HPA is configured automatically (2-10 replicas)
kubectl get hpa

# View HPA metrics
kubectl describe hpa threat-detector-inference-hpa
```

---

## Cloud Platforms

### AWS (EKS)

```bash
# Create EKS cluster
eksctl create cluster \
  --name threat-detector \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type c5.2xlarge \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 10

# Configure kubectl
aws eks update-kubeconfig --name threat-detector --region us-east-1

# Deploy application
kubectl apply -f deployment/kubernetes/
```

### GCP (GKE)

```bash
# Create GKE cluster
gcloud container clusters create threat-detector \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials threat-detector

# Deploy application
kubectl apply -f deployment/kubernetes/
```

### Azure (AKS)

```bash
# Create AKS cluster
az aks create \
  --resource-group threat-detector-rg \
  --name threat-detector \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 10

# Get credentials
az aks get-credentials --resource-group threat-detector-rg --name threat-detector

# Deploy application
kubectl apply -f deployment/kubernetes/
```

---

## Configuration

### Environment Variables

Key configuration variables:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Redis
REDIS_URL=redis://redis:6379/0

# Database
DB_HOST=postgres
DB_PORT=5432
DB_DATABASE=threat_detection
DB_USERNAME=detector
DB_PASSWORD=<secure-password>

# Models
MODEL_THREAT_THRESHOLD=0.85
MODEL_ANOMALY_THRESHOLD=1.0

# SIEM Integration
SIEM_SPLUNK_HEC_URL=https://splunk:8088/services/collector
SIEM_SPLUNK_HEC_TOKEN=<your-token>
```

### Resource Limits

**Inference Server (Kubernetes):**

```yaml
resources:
  requests:
    cpu: 1000m      # 1 CPU
    memory: 2Gi     # 2 GB
  limits:
    cpu: 2000m      # 2 CPUs
    memory: 4Gi     # 4 GB
```

Adjust based on your load requirements.

---

## Monitoring Setup

### Prometheus

```bash
# Install Prometheus Operator
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack

# Port forward to access
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
```

### Grafana Dashboards

```bash
# Access Grafana
kubectl port-forward svc/prometheus-grafana 3000:80

# Default credentials: admin/prom-operator

# Import dashboards from deployment/monitoring/grafana/
```

### Alert Rules

```bash
# Apply alert rules
kubectl apply -f deployment/monitoring/prometheus/alert-rules.yaml

# Verify rules
kubectl get prometheusrules
```

---

## Troubleshooting

### Common Issues

**1. Pods not starting**

```bash
# Check pod status
kubectl describe pod <pod-name>

# Check logs
kubectl logs <pod-name>

# Common causes:
# - Image pull errors
# - Resource limits
# - Configuration errors
```

**2. High latency**

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# Scale up if needed
kubectl scale deployment threat-detector-inference --replicas=8

# Check HPA status
kubectl describe hpa
```

**3. Models not loading**

```bash
# Verify models are mounted
kubectl exec -it <pod-name> -- ls -la /app/models/

# Check PVC
kubectl get pvc

# Common fix: Train models first
jupyter notebook notebooks/01_model_training_demo.ipynb
```

**4. Database connection errors**

```bash
# Test connectivity
kubectl exec -it <pod-name> -- nc -zv postgres-service 5432

# Check credentials
kubectl get secret threat-detector-secrets -o yaml

# Verify service
kubectl get svc postgres-service
```

### Debug Mode

Enable debug logging:

```bash
kubectl set env deployment/threat-detector-inference DEBUG=true LOG_LEVEL=debug

# Watch logs
kubectl logs -f deployment/threat-detector-inference
```

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check readiness
curl http://localhost:8000/ready

# Check metrics
curl http://localhost:8000/metrics
```

---

## Backup and Restore

### Backing Up Models

```bash
# Backup models directory
kubectl exec -it <pod-name> -- tar czf /tmp/models-backup.tar.gz /app/models/
kubectl cp <pod-name>:/tmp/models-backup.tar.gz ./models-backup.tar.gz
```

### Backing Up Database

```bash
# PostgreSQL backup
kubectl exec -it postgres-pod -- pg_dump -U detector threat_detection > backup.sql

# Restore
kubectl exec -i postgres-pod -- psql -U detector threat_detection < backup.sql
```

---

## Production Checklist

Before going to production:

- [ ] Environment variables configured
- [ ] Secrets created and secured
- [ ] Models trained and deployed
- [ ] Resource limits set appropriately
- [ ] Monitoring and alerting configured
- [ ] Logging centralized
- [ ] Backups automated
- [ ] Disaster recovery tested
- [ ] Security scan passed
- [ ] Load testing completed
- [ ] Documentation updated
- [ ] Runbooks created
- [ ] On-call rotation established

---

## Next Steps

- [Operations Guide](docs/operations.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
- [Performance Tuning](docs/performance.md)

---

**Version**: 1.0.0
**Last Updated**: 2025-11-15
