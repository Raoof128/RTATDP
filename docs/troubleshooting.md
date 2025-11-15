# Troubleshooting Guide

Common issues and their solutions for the AI Threat Detection Pipeline.

## Table of Contents

1. [General Troubleshooting](#general-troubleshooting)
2. [API Issues](#api-issues)
3. [Data Pipeline Issues](#data-pipeline-issues)
4. [Model Issues](#model-issues)
5. [Performance Issues](#performance-issues)
6. [Integration Issues](#integration-issues)
7. [Infrastructure Issues](#infrastructure-issues)

---

## General Troubleshooting

### Check System Health

```bash
# Run health check script
bash scripts/health_check.sh

# Check all service statuses
docker-compose ps

# Kubernetes
kubectl get pods -n security
kubectl get services -n security
```

### View Logs

```bash
# Docker Compose
docker-compose logs -f inference-server

# Kubernetes
kubectl logs -f deployment/threat-detector-inference -n security

# View all pod logs
kubectl logs -l app=threat-detector --tail=100
```

### Check Resource Usage

```bash
# Docker
docker stats

# Kubernetes
kubectl top pods -n security
kubectl top nodes
```

---

## API Issues

### Issue: API Returns 503 "Models not loaded"

**Symptoms:**
- API returns 503 status code
- Error message: "Models not loaded"

**Cause:**
- Model files not present in models directory
- Models not trained yet

**Solution:**

```bash
# Option 1: Train models
jupyter notebook notebooks/01_model_training_demo.ipynb

# Option 2: Mount pre-trained models
# Ensure models/ensemble/ and models/anomaly/ contain .pkl files

# Verify models exist
ls -la models/ensemble/
ls -la models/anomaly/

# Restart API server
docker-compose restart inference-server
```

### Issue: API Slow Response Times

**Symptoms:**
- Inference time > 500ms
- Timeout errors

**Diagnosis:**

```bash
# Check metrics endpoint
curl http://localhost:8000/metrics | grep inference_latency

# Check resource usage
docker stats inference-server
```

**Solutions:**

```bash
# 1. Scale up workers
# Edit docker-compose.yml
# CMD ["uvicorn", "src.inference_server.api:app", "--workers", "8"]

# 2. Increase resources
docker update --cpus="4" --memory="8g" inference-server

# 3. Enable caching
# Set PERF_ENABLE_CACHING=true in .env

# 4. Check Redis connection
docker-compose logs redis
```

### Issue: 422 Validation Errors

**Symptoms:**
- POST /predict returns 422
- "Validation error" message

**Common Causes:**

1. **Invalid IP address format**
```json
// ❌ Wrong
{"source_ip": "invalid.ip.address"}

// ✅ Correct
{"source_ip": "192.168.1.100"}
```

2. **Port out of range**
```json
// ❌ Wrong
{"source_port": 99999}

// ✅ Correct
{"source_port": 54321}
```

3. **Missing required fields**
```bash
# Check API docs for required fields
curl http://localhost:8000/docs
```

---

## Data Pipeline Issues

### Issue: Kafka Connection Failed

**Symptoms:**
- "Cannot connect to Kafka" errors
- Producer/consumer errors

**Diagnosis:**

```bash
# Check if Kafka is running
docker-compose ps kafka

# Check Kafka logs
docker-compose logs kafka

# Test connection
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

**Solutions:**

```bash
# 1. Restart Kafka
docker-compose restart kafka zookeeper

# 2. Recreate topics
make kafka-create-topics

# 3. Check network connectivity
docker-compose exec inference-server nc -zv kafka 9093

# 4. Verify bootstrap servers
echo $KAFKA_BOOTSTRAP_SERVERS
```

### Issue: Events Not Being Consumed

**Symptoms:**
- No alerts generated
- Consumer lag increasing

**Diagnosis:**

```bash
# Check consumer groups
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Check lag
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group threat-detection-consumer \
  --describe
```

**Solutions:**

```bash
# 1. Check if topics exist
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# 2. Reset consumer offset (CAUTION: data loss)
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group threat-detection-consumer \
  --reset-offsets \
  --to-latest \
  --execute \
  --all-topics

# 3. Scale consumers
kubectl scale deployment threat-detector-inference --replicas=5
```

### Issue: Redis Connection Timeout

**Symptoms:**
- "Connection timeout" errors
- Feature extraction failures

**Diagnosis:**

```bash
# Test Redis connection
docker-compose exec inference-server redis-cli -h redis ping

# Check Redis status
docker-compose exec redis redis-cli INFO
```

**Solutions:**

```bash
# 1. Restart Redis
docker-compose restart redis

# 2. Check Redis memory
docker-compose exec redis redis-cli INFO memory

# 3. Clear Redis if needed
docker-compose exec redis redis-cli FLUSHALL

# 4. Increase max connections
# Edit redis.conf: maxclients 10000
```

---

## Model Issues

### Issue: Low Prediction Accuracy

**Symptoms:**
- Accuracy < 90%
- High false positive rate

**Diagnosis:**

```python
# Evaluate model performance
from src.models.ensemble_model import EnsembleDetector

detector = EnsembleDetector(model_path="models/ensemble")
metrics = detector.evaluate(X_test, y_test)
print(metrics)
```

**Solutions:**

```bash
# 1. Retrain models with more data
# Collect more labeled samples

# 2. Tune hyperparameters
# Edit src/models/ensemble_model.py

# 3. Check for data drift
# Compare feature distributions

# 4. Add more features
# Edit src/feature_engineering/feature_extractor.py
```

### Issue: High False Positive Rate

**Symptoms:**
- FPR > 5%
- Too many benign events flagged as threats

**Solutions:**

```bash
# 1. Adjust threat threshold
# Set MODEL_THREAT_THRESHOLD=0.90 in .env (increase from 0.85)

# 2. Retrain with balanced dataset
# Ensure equal representation of threat/benign samples

# 3. Fine-tune anomaly contamination
# Set MODEL_ANOMALY_CONTAMINATION=0.01 (decrease from 0.02)

# 4. Review feature importance
# Remove noisy features
```

### Issue: Model File Not Found

**Symptoms:**
- FileNotFoundError when loading models
- "Model directory not found" errors

**Solutions:**

```bash
# 1. Check model path
ls -la models/ensemble/
ls -la models/anomaly/

# 2. Train models if missing
jupyter notebook notebooks/01_model_training_demo.ipynb

# 3. Fix permissions
chmod -R 755 models/

# 4. Mount volumes correctly (Docker)
# Verify docker-compose.yml volumes section
```

---

## Performance Issues

### Issue: High Memory Usage

**Symptoms:**
- OOMKilled errors
- Memory usage > 90%

**Diagnosis:**

```bash
# Check memory usage
docker stats inference-server

# Kubernetes
kubectl top pod threat-detector-inference-xxx
```

**Solutions:**

```bash
# 1. Increase memory limit
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G

# 2. Reduce batch size
# Set PERF_BATCH_SIZE=64 in .env (default: 128)

# 3. Enable feature caching expiration
# Set REDIS_DEFAULT_TTL=1800 (30 minutes)

# 4. Optimize model loading
# Load models on startup, not per request
```

### Issue: High CPU Usage

**Symptoms:**
- CPU usage > 90%
- Slow request processing

**Solutions:**

```bash
# 1. Scale horizontally
kubectl scale deployment threat-detector-inference --replicas=8

# 2. Optimize inference
# Use ONNX models for faster inference
# Convert: python scripts/convert_to_onnx.py

# 3. Enable request batching
# Set PERF_BATCH_SIZE=256

# 4. Profile code
python -m cProfile -o profile.stats src/inference_server/api.py
```

### Issue: Slow Startup Time

**Symptoms:**
- Pods take > 2 minutes to start
- Readiness probe failures

**Solutions:**

```bash
# 1. Pre-download dependencies
# Use Docker layer caching

# 2. Optimize model loading
# Use pickle protocol 4 or higher
# Compress models

# 3. Adjust probe timings
# Increase initialDelaySeconds in K8s manifest
initialDelaySeconds: 60

# 4. Use smaller model files
# Reduce n_estimators in ensemble models
```

---

## Integration Issues

### Issue: Splunk HEC Connection Failed

**Symptoms:**
- "Connection refused" errors
- Alerts not appearing in Splunk

**Diagnosis:**

```bash
# Test HEC endpoint
curl -k https://splunk:8088/services/collector/health

# Test with token
curl -k https://splunk:8088/services/collector \
  -H "Authorization: Splunk YOUR_TOKEN" \
  -d '{"event": "test"}'
```

**Solutions:**

```bash
# 1. Verify HEC URL and token
echo $SIEM_SPLUNK_HEC_URL
echo $SIEM_SPLUNK_HEC_TOKEN

# 2. Check SSL verification
# Set verify_ssl=False for self-signed certificates

# 3. Check network connectivity
docker-compose exec inference-server curl https://splunk:8088

# 4. Verify index exists in Splunk
# Create "security" index if missing
```

### Issue: TheHive Case Creation Failed

**Symptoms:**
- Cases not created
- "Authentication failed" errors

**Solutions:**

```bash
# 1. Verify API key
echo $SIEM_THEHIVE_API_KEY

# 2. Test API endpoint
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://thehive:9000/api/case

# 3. Check permissions
# Ensure API key has case creation permissions

# 4. Review case creation logs
docker-compose logs inference-server | grep thehive
```

---

## Infrastructure Issues

### Issue: Kubernetes Pods CrashLooping

**Symptoms:**
- Pods restart repeatedly
- CrashLoopBackOff status

**Diagnosis:**

```bash
# Get pod status
kubectl get pods -n security

# Describe pod
kubectl describe pod <pod-name> -n security

# Check logs
kubectl logs <pod-name> -n security --previous
```

**Common Causes & Solutions:**

1. **Missing secrets**
```bash
kubectl get secrets -n security
kubectl create secret generic threat-detector-secrets --from-env-file=.env
```

2. **Resource limits too low**
```bash
# Edit deployment.yaml
resources:
  limits:
    memory: 8Gi  # Increase from 4Gi
```

3. **Health check failures**
```bash
# Increase timeout
livenessProbe:
  initialDelaySeconds: 60  # Increase from 30
```

### Issue: Persistent Volume Claims Pending

**Symptoms:**
- PVC stuck in Pending state
- Models not persisting

**Solutions:**

```bash
# 1. Check PVC status
kubectl get pvc -n security
kubectl describe pvc threat-detector-models-pvc

# 2. Check storage class
kubectl get storageclass

# 3. Create storage class if missing
kubectl apply -f deployment/kubernetes/storageclass.yaml

# 4. Verify provisioner
kubectl get pods -n kube-system | grep provisioner
```

### Issue: LoadBalancer Pending

**Symptoms:**
- Service stuck in Pending state
- External IP not assigned

**Solutions:**

```bash
# 1. Check if cloud provider supports LoadBalancer
kubectl get svc -n security

# 2. Use NodePort instead
# Edit service.yaml: type: NodePort

# 3. Use Ingress controller
kubectl apply -f deployment/kubernetes/ingress.yaml

# 4. Check cloud provider quota
# Ensure LoadBalancer quota not exceeded
```

---

## Debug Mode

### Enable Debug Logging

```bash
# Docker Compose
# Edit .env
DEBUG=true
LOG_LEVEL=debug

# Restart services
docker-compose restart

# Kubernetes
kubectl set env deployment/threat-detector-inference \
  DEBUG=true \
  LOG_LEVEL=debug \
  -n security
```

### Verbose Output

```python
# In Python code
import logging
logging.basicConfig(level=logging.DEBUG)

# Check logs
docker-compose logs -f inference-server
```

---

## Getting Help

### Information to Collect

When reporting issues, include:

1. **Environment**
   - OS and version
   - Docker/Kubernetes version
   - Python version

2. **Logs**
   ```bash
   docker-compose logs > logs.txt
   kubectl logs <pod> -n security > k8s-logs.txt
   ```

3. **Configuration**
   ```bash
   # Sanitize sensitive data first
   cat .env | grep -v PASSWORD | grep -v TOKEN
   ```

4. **Metrics**
   ```bash
   curl http://localhost:8000/metrics > metrics.txt
   ```

5. **Resource Usage**
   ```bash
   docker stats --no-stream > docker-stats.txt
   kubectl top pods -n security > k8s-resources.txt
   ```

### Support Channels

- GitHub Issues: Report bugs and feature requests
- Documentation: Check docs/ directory
- Examples: Review examples/ directory

---

## Common Commands

```bash
# Restart everything
make docker-down && make docker-up

# Clear all data (CAUTION)
docker-compose down -v

# Reset Kafka topics
make kafka-create-topics

# Rebuild images
make docker-build-no-cache

# Run full test suite
make test

# Check code quality
make lint

# Format code
make format
```

---

**Version**: 1.0.0
**Last Updated**: 2025-11-15
