# Operations Runbook

Standard operating procedures for managing the AI Threat Detection Pipeline in production.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Model Management](#model-management)
3. [Incident Response](#incident-response)
4. [Maintenance](#maintenance)
5. [Monitoring](#monitoring)
6. [Backup & Recovery](#backup--recovery)
7. [Scaling](#scaling)

---

## Daily Operations

### Morning Checklist

```bash
# 1. Check system health
bash scripts/health_check.sh

# 2. Review metrics dashboard
# Open Grafana: http://grafana-url:3000

# 3. Check alert queue
curl http://api-url:8000/metrics | grep alerts_total

# 4. Review error logs
kubectl logs -l app=threat-detector --since=24h | grep ERROR

# 5. Verify SIEM integration
# Check Splunk for recent alerts

# 6. Check resource usage
kubectl top pods -n security
kubectl top nodes
```

### Evening Checklist

```bash
# 1. Review day's statistics
curl http://api-url:8000/metrics > daily-metrics-$(date +%Y%m%d).txt

# 2. Check for failed alerts
kubectl logs -l app=threat-detector --since=12h | grep -i "failed\|error"

# 3. Verify backup completion
# Check backup logs

# 4. Review capacity planning
kubectl describe hpa threat-detector-inference-hpa

# 5. Check for pending updates
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}' | tr -s '[[:space:]]' '\n' | sort | uniq
```

---

## Model Management

### Model Training Schedule

**Weekly**: Retrain models with latest data
**Daily**: Evaluate model performance
**Monthly**: Full model audit and optimization

### Retraining Workflow

```bash
# 1. Collect training data
python scripts/collect_training_data.py --days 30 --output data/training/

# 2. Train ensemble models
jupyter nbconvert --execute --to notebook \
  notebooks/01_model_training_demo.ipynb

# 3. Evaluate new models
python scripts/evaluate_models.py \
  --test-data data/test/recent.parquet \
  --model-dir models/ensemble-new/

# 4. Compare performance
python scripts/compare_models.py \
  --baseline models/ensemble/ \
  --candidate models/ensemble-new/

# 5. Deploy if improved (canary)
kubectl set image deployment/threat-detector-inference \
  inference-server=threat-detector:1.1.0-canary

# 6. Monitor canary metrics (24 hours)
# Check Grafana dashboard for accuracy/latency

# 7. Full rollout if successful
kubectl set image deployment/threat-detector-inference \
  inference-server=threat-detector:1.1.0

# 8. Rollback if issues
kubectl rollout undo deployment/threat-detector-inference
```

### Model Performance Monitoring

```bash
# Daily model metrics
curl http://api-url:8000/model/info

# Check accuracy trend
# Prometheus query:
# rate(predictions_correct_total[24h]) / rate(predictions_total[24h])

# Alert on accuracy drop
# Alert if accuracy < 0.90 for 1 hour
```

---

## Incident Response

### Severity Levels

| Severity | Definition | Response Time | Example |
|----------|-----------|---------------|---------|
| P0 | System down | 15 minutes | API not responding |
| P1 | Major degradation | 1 hour | Accuracy < 70% |
| P2 | Partial degradation | 4 hours | High latency |
| P3 | Minor issue | 24 hours | Slow dashboard |

### P0: System Down

**Symptoms:**
- API health check fails
- No alerts being generated
- All pods down

**Response:**

```bash
# 1. Check system status
kubectl get pods -n security

# 2. Check recent changes
kubectl rollout history deployment/threat-detector-inference

# 3. Rollback if recent deploy
kubectl rollout undo deployment/threat-detector-inference

# 4. Check resource limits
kubectl describe nodes

# 5. Scale up if needed
kubectl scale deployment threat-detector-inference --replicas=8

# 6. Notify team
# Send alert to #incidents channel

# 7. Create incident ticket
# Document timeline and actions
```

### P1: Model Accuracy Degradation

**Symptoms:**
- Accuracy drops below 90%
- High false positive rate
- User complaints

**Response:**

```bash
# 1. Check model metrics
curl http://api-url:8000/metrics | grep model_accuracy

# 2. Review recent predictions
# Query alert database for recent false positives

# 3. Check for data drift
python scripts/check_drift.py

# 4. Temporary mitigation
# Adjust threshold: MODEL_THREAT_THRESHOLD=0.90

# 5. Schedule retraining
# Add to urgent backlog

# 6. Notify stakeholders
# Email security team with impact assessment
```

### P2: High Latency

**Symptoms:**
- P95 latency > 200ms
- Timeouts increasing
- Queue backup

**Response:**

```bash
# 1. Check current load
kubectl top pods
curl http://api-url:8000/metrics | grep inference_latency

# 2. Scale horizontally
kubectl scale deployment threat-detector-inference --replicas=10

# 3. Check Redis performance
docker-compose exec redis redis-cli INFO stats

# 4. Check for slow queries
# Review application logs

# 5. Monitor improvement
# Watch Grafana latency dashboard

# 6. Investigate root cause
# Schedule post-incident review
```

---

## Maintenance

### Weekly Maintenance Window

**Time**: Sunday 02:00-04:00 UTC
**Duration**: 2 hours
**Notification**: 7 days advance notice

**Tasks:**

```bash
# 1. Apply security patches
kubectl set image deployment/threat-detector-inference \
  inference-server=threat-detector:1.0.1

# 2. Update dependencies
pip install -U -r requirements.txt
docker build -t threat-detector:latest .

# 3. Optimize databases
kubectl exec -it postgres-pod -- vacuumdb -U detector threat_detection

# 4. Clean old data
kubectl exec -it postgres-pod -- psql -U detector -d threat_detection \
  -c "DELETE FROM alerts WHERE timestamp < NOW() - INTERVAL '90 days';"

# 5. Prune Docker images
docker system prune -af --volumes

# 6. Verify backups
bash scripts/verify_backups.sh

# 7. Run health checks
bash scripts/health_check.sh
```

### Monthly Tasks

```bash
# 1. Full model retraining
# Execute training pipeline

# 2. Security audit
make security-scan
trivy image threat-detector:latest

# 3. Performance review
# Generate performance report
python scripts/generate_perf_report.py --month $(date +%Y-%m)

# 4. Capacity planning
# Review growth trends and forecast

# 5. Documentation update
# Update runbooks with learnings

# 6. Team training
# Share incident learnings
```

---

## Monitoring

### Key Metrics

**System Health:**
```promql
# API Uptime
up{job="threat-detector-inference"}

# Error Rate
rate(http_requests_total{status=~"5.."}[5m])

# Request Rate
rate(http_requests_total[5m])
```

**Model Performance:**
```promql
# Inference Latency
histogram_quantile(0.95, inference_latency_seconds_bucket)

# Throughput
rate(predictions_total[5m])

# Accuracy (requires custom metric)
model_accuracy_gauge
```

**Resource Usage:**
```promql
# CPU Usage
container_cpu_usage_seconds_total{pod=~"threat-detector.*"}

# Memory Usage
container_memory_usage_bytes{pod=~"threat-detector.*"}

# Disk I/O
rate(container_fs_reads_bytes_total[5m])
```

### Alerting Rules

**Critical Alerts:**

```yaml
# API Down
- alert: APIDown
  expr: up{job="threat-detector-inference"} == 0
  for: 5m
  annotations:
    summary: "API is down"
    action: "Run incident response P0"

# High Error Rate
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 10m
  annotations:
    summary: "Error rate > 5%"

# Model Accuracy Drop
- alert: LowAccuracy
  expr: model_accuracy_gauge < 0.90
  for: 1h
  annotations:
    summary: "Model accuracy < 90%"
```

**Warning Alerts:**

```yaml
# High Latency
- alert: HighLatency
  expr: histogram_quantile(0.95, inference_latency_seconds_bucket) > 0.2
  for: 15m
  annotations:
    summary: "P95 latency > 200ms"

# High Memory Usage
- alert: HighMemory
  expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85
  for: 10m
  annotations:
    summary: "Memory usage > 85%"
```

---

## Backup & Recovery

### Backup Schedule

| Component | Frequency | Retention | Location |
|-----------|-----------|-----------|----------|
| Models | Daily | 30 days | S3/GCS |
| Database | Hourly | 7 days | S3/GCS |
| Configuration | On change | Forever | Git |
| Logs | Continuous | 30 days | ELK/Loki |

### Backup Procedures

**Models:**

```bash
# Daily backup (automated via cron)
#!/bin/bash
DATE=$(date +%Y%m%d)
tar czf models-backup-$DATE.tar.gz models/
aws s3 cp models-backup-$DATE.tar.gz s3://backups/models/
# Cleanup old backups
find . -name "models-backup-*.tar.gz" -mtime +30 -delete
```

**Database:**

```bash
# Hourly backup (automated)
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d-%H%M)
pg_dump -U detector threat_detection | gzip > backup-$TIMESTAMP.sql.gz
aws s3 cp backup-$TIMESTAMP.sql.gz s3://backups/database/
# Cleanup old backups
find . -name "backup-*.sql.gz" -mtime +7 -delete
```

### Recovery Procedures

**Restore Models:**

```bash
# 1. Download backup
aws s3 cp s3://backups/models/models-backup-20251115.tar.gz .

# 2. Extract
tar xzf models-backup-20251115.tar.gz

# 3. Verify models
ls -la models/ensemble/
ls -la models/anomaly/

# 4. Restart services
kubectl rollout restart deployment/threat-detector-inference
```

**Restore Database:**

```bash
# 1. Download backup
aws s3 cp s3://backups/database/backup-20251115-1200.sql.gz .

# 2. Restore
gunzip < backup-20251115-1200.sql.gz | \
  kubectl exec -i postgres-pod -- psql -U detector threat_detection

# 3. Verify data
kubectl exec -it postgres-pod -- psql -U detector -d threat_detection \
  -c "SELECT COUNT(*) FROM alerts;"
```

### Disaster Recovery Test

**Quarterly Test:**

```bash
# 1. Simulate failure (staging environment)
kubectl delete namespace security

# 2. Restore from backup
bash scripts/disaster_recovery.sh

# 3. Verify system
bash scripts/health_check.sh

# 4. Document recovery time
# RTO achieved: ____ minutes
# RPO achieved: ____ minutes

# 5. Update DR plan based on learnings
```

---

## Scaling

### Auto-Scaling Configuration

**HPA Settings:**

```yaml
minReplicas: 2
maxReplicas: 10
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: inference_latency_p95
      target:
        type: AverageValue
        averageValue: "100m"  # 100ms
```

### Manual Scaling

**Scale Up:**

```bash
# Immediate scale up for traffic spike
kubectl scale deployment threat-detector-inference --replicas=15

# Verify scaling
kubectl get pods -w

# Monitor performance
watch kubectl top pods
```

**Scale Down:**

```bash
# Gradual scale down during low traffic
kubectl scale deployment threat-detector-inference --replicas=3

# Ensure no disruption
kubectl get pods -o wide
```

### Vertical Scaling

**Increase Resources:**

```bash
# Edit deployment
kubectl edit deployment threat-detector-inference

# Update resources
resources:
  requests:
    cpu: 2000m
    memory: 4Gi
  limits:
    cpu: 4000m
    memory: 8Gi

# Apply changes
kubectl rollout status deployment/threat-detector-inference
```

---

## On-Call Rotation

### Primary On-Call

- Monitor alerts 24/7
- Respond to P0/P1 incidents
- Escalate as needed
- Update incident tickets

### Secondary On-Call

- Backup for primary
- Handle P2/P3 incidents
- Assist with investigations

### Escalation Path

```
P0: Primary → Secondary → Engineering Lead → VP Engineering
P1: Primary → Engineering Lead
P2: Primary → Schedule for next business day
P3: Add to backlog
```

---

## Runbook Quick Reference

| Scenario | Action | Reference |
|----------|--------|-----------|
| API Down | `kubectl rollout undo` | [P0 Response](#p0-system-down) |
| High Latency | `kubectl scale --replicas=10` | [P2 Response](#p2-high-latency) |
| Low Accuracy | Adjust threshold, retrain | [P1 Response](#p1-model-accuracy-degradation) |
| Out of Memory | Increase limits, restart | [Troubleshooting](troubleshooting.md) |
| Kafka Lag | Scale consumers | [Data Pipeline Issues](troubleshooting.md#data-pipeline-issues) |

---

**Version**: 1.0.0
**Last Updated**: 2025-11-15
**Review Schedule**: Quarterly
