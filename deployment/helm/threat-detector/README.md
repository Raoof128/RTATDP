# AI Threat Detection Pipeline - Helm Chart

Production-grade Helm chart for deploying the AI Threat Detection Pipeline on Kubernetes.

## Overview

This Helm chart deploys a complete AI-powered threat detection system with:
- FastAPI inference server with auto-scaling
- Kafka event streaming
- Redis feature caching
- Prometheus monitoring
- Grafana dashboards
- Automated health checks and recovery

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PV provisioner support (for persistent storage)
- Minimum cluster resources:
  - 4 CPU cores
  - 8GB RAM
  - 50GB storage

## Installation

### Quick Start

```bash
# Add the Helm repository (if published)
helm repo add threat-detector https://charts.example.com
helm repo update

# Install with default values
helm install my-threat-detector threat-detector/threat-detector

# Install with custom values
helm install my-threat-detector threat-detector/threat-detector -f custom-values.yaml
```

### Local Installation

```bash
# From the repository root
helm install my-threat-detector ./deployment/helm/threat-detector

# With custom namespace
kubectl create namespace security
helm install my-threat-detector ./deployment/helm/threat-detector -n security
```

## Configuration

### Essential Configuration

Create a `custom-values.yaml` file:

```yaml
# Production environment
global:
  environment: production
  storageClass: fast-ssd

# Inference server scaling
inferenceServer:
  replicaCount: 5
  autoscaling:
    minReplicas: 3
    maxReplicas: 20

# Configure ingress
inferenceServer:
  ingress:
    enabled: true
    hosts:
      - host: threat-detector.mycompany.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: threat-detector-tls
        hosts:
          - threat-detector.mycompany.com

# External Kafka (disable built-in)
kafka:
  enabled: false
config:
  kafka:
    bootstrapServers: "kafka-prod.mycompany.com:9092"

# External Redis (disable built-in)
redis:
  enabled: false
config:
  redis:
    host: "redis-prod.mycompany.com"
    port: 6379

# Secrets from external secrets manager
secrets:
  existingSecret: "threat-detector-prod-secrets"
```

Apply configuration:

```bash
helm install my-threat-detector ./deployment/helm/threat-detector -f custom-values.yaml
```

### Parameters

#### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.environment` | Environment name | `production` |
| `global.storageClass` | Storage class for PVCs | `standard` |

#### Inference Server Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `inferenceServer.enabled` | Enable inference server | `true` |
| `inferenceServer.replicaCount` | Number of replicas | `3` |
| `inferenceServer.image.repository` | Image repository | `threat-detector/inference-server` |
| `inferenceServer.image.tag` | Image tag | `1.0.0` |
| `inferenceServer.resources.requests.cpu` | CPU request | `500m` |
| `inferenceServer.resources.requests.memory` | Memory request | `2Gi` |
| `inferenceServer.resources.limits.cpu` | CPU limit | `2000m` |
| `inferenceServer.resources.limits.memory` | Memory limit | `4Gi` |

#### Autoscaling Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `inferenceServer.autoscaling.enabled` | Enable HPA | `true` |
| `inferenceServer.autoscaling.minReplicas` | Minimum replicas | `2` |
| `inferenceServer.autoscaling.maxReplicas` | Maximum replicas | `10` |
| `inferenceServer.autoscaling.targetCPUUtilizationPercentage` | Target CPU % | `70` |
| `inferenceServer.autoscaling.targetMemoryUtilizationPercentage` | Target memory % | `80` |

#### Kafka Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `kafka.enabled` | Deploy Kafka with chart | `true` |
| `config.kafka.bootstrapServers` | Kafka bootstrap servers | `kafka:9092` |
| `config.kafka.topics.network` | Network events topic | `security.events.network` |
| `config.kafka.topics.endpoint` | Endpoint events topic | `security.events.endpoint` |
| `config.kafka.topics.application` | Application logs topic | `security.events.application` |

#### Redis Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Deploy Redis with chart | `true` |
| `config.redis.host` | Redis host | `redis-master` |
| `config.redis.port` | Redis port | `6379` |
| `config.redis.ttl` | Cache TTL (seconds) | `3600` |

#### Monitoring Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `prometheus.enabled` | Deploy Prometheus | `true` |
| `grafana.enabled` | Deploy Grafana | `true` |
| `serviceMonitor.enabled` | Create ServiceMonitor | `true` |

## Upgrading

```bash
# Upgrade to new version
helm upgrade my-threat-detector ./deployment/helm/threat-detector

# Upgrade with new values
helm upgrade my-threat-detector ./deployment/helm/threat-detector -f new-values.yaml

# Rollback to previous version
helm rollback my-threat-detector
```

## Uninstallation

```bash
# Uninstall release
helm uninstall my-threat-detector

# Uninstall and delete PVCs
helm uninstall my-threat-detector
kubectl delete pvc -l app.kubernetes.io/instance=my-threat-detector
```

## Post-Installation

### 1. Verify Deployment

```bash
# Check pods status
kubectl get pods -l app.kubernetes.io/name=threat-detector

# Check services
kubectl get svc -l app.kubernetes.io/name=threat-detector

# View logs
kubectl logs -l app.kubernetes.io/name=threat-detector --tail=100
```

### 2. Upload ML Models

```bash
# Create a pod to upload models
kubectl run model-upload --rm -it --image=busybox \
  --overrides='{"spec":{"volumes":[{"name":"models","persistentVolumeClaim":{"claimName":"my-threat-detector-models"}}],"containers":[{"name":"upload","image":"busybox","volumeMounts":[{"name":"models","mountPath":"/models"}]}]}}'

# Copy models from local machine
kubectl cp ./models/ensemble my-threat-detector-0:/app/models/ensemble
kubectl cp ./models/anomaly my-threat-detector-0:/app/models/anomaly

# Restart pods to load models
kubectl rollout restart deployment/my-threat-detector
```

### 3. Access the API

```bash
# Port-forward for local access
kubectl port-forward svc/my-threat-detector 8000:8000

# Test the API
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

### 4. Access Monitoring

```bash
# Port-forward Grafana
kubectl port-forward svc/my-threat-detector-grafana 3000:80

# Open browser to http://localhost:3000
# Default credentials: admin/changeme (change in values.yaml)
```

## Production Recommendations

### Security

1. **Use External Secrets Manager**:
   ```yaml
   secrets:
     existingSecret: "threat-detector-secrets"
   ```

2. **Enable TLS**:
   ```yaml
   inferenceServer:
     ingress:
       tls:
         - secretName: threat-detector-tls
   ```

3. **Enable Network Policies**:
   ```yaml
   networkPolicy:
     enabled: true
   ```

### High Availability

1. **Multi-replica deployment**:
   ```yaml
   inferenceServer:
     replicaCount: 5
     autoscaling:
       minReplicas: 3
       maxReplicas: 20
   ```

2. **Pod Disruption Budget**:
   ```yaml
   podDisruptionBudget:
     enabled: true
     minAvailable: 2
   ```

3. **Anti-affinity rules** (already configured in defaults)

### Performance

1. **Use fast storage**:
   ```yaml
   global:
     storageClass: fast-ssd
   persistence:
     size: 50Gi
   ```

2. **Increase resources**:
   ```yaml
   inferenceServer:
     resources:
       requests:
         cpu: 2000m
         memory: 4Gi
       limits:
         cpu: 4000m
         memory: 8Gi
   ```

3. **Optimize Kafka**:
   ```yaml
   kafka:
     replicaCount: 5
     resources:
       requests:
         cpu: 1000m
         memory: 4Gi
   ```

## Troubleshooting

### Pods not starting

```bash
# Check events
kubectl describe pod <pod-name>

# Check logs
kubectl logs <pod-name>

# Common issue: PVC not bound
kubectl get pvc
kubectl describe pvc my-threat-detector-models
```

### Models not loading

```bash
# Check if models exist in PVC
kubectl exec -it <pod-name> -- ls -la /app/models

# Check model paths in config
kubectl get configmap my-threat-detector-config -o yaml
```

### High latency

```bash
# Check pod resources
kubectl top pods

# Scale up
kubectl scale deployment my-threat-detector --replicas=10

# Or update HPA
helm upgrade my-threat-detector ./deployment/helm/threat-detector \
  --set inferenceServer.autoscaling.maxReplicas=20
```

## Support

- Documentation: [docs/](../../docs/)
- Issues: GitHub Issues
- Email: security@example.com

## License

Apache-2.0
