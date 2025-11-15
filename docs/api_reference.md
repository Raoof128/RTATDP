# API Reference

Complete API reference for the AI Threat Detection Pipeline inference server.

## Base URL

```
http://localhost:8000
```

Production: `https://threat-detector.yourcompany.com`

## Authentication

Currently, the API does not require authentication for local development. In production, implement:
- API keys via headers (`X-API-Key`)
- JWT tokens
- OAuth 2.0

## Content Type

All endpoints accept and return `application/json` unless otherwise specified.

## Rate Limiting

Production deployments should implement rate limiting:
- Default: 100 requests/minute per IP
- Configurable via Nginx ingress annotations

---

## Health & Status Endpoints

### GET /

Root endpoint with service information.

**Response**

```json
{
  "service": "AI Threat Detection API",
  "version": "1.0.0",
  "status": "operational",
  "documentation": "/docs"
}
```

**Example**

```bash
curl http://localhost:8000/
```

---

### GET /health

Health check endpoint for monitoring and load balancers.

**Response**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T14:30:22.123Z",
  "models_loaded": {
    "ensemble": true,
    "anomaly": true
  },
  "uptime_seconds": 3600
}
```

**Status Codes**
- `200` - Service healthy
- `503` - Service unhealthy (models not loaded, dependencies unavailable)

**Example**

```bash
curl http://localhost:8000/health
```

---

### GET /ready

Readiness check for Kubernetes readiness probes.

**Response**

```json
{
  "ready": true,
  "models_loaded": true,
  "dependencies": {
    "redis": "connected",
    "kafka": "connected"
  }
}
```

**Status Codes**
- `200` - Service ready to accept traffic
- `503` - Service not ready (still initializing)

**Example**

```bash
curl http://localhost:8000/ready
```

---

## Model Information

### GET /model/info

Get information about loaded ML models.

**Response**

```json
{
  "ensemble_model": {
    "type": "VotingClassifier",
    "estimators": ["RandomForest", "XGBoost", "LightGBM"],
    "loaded": true
  },
  "anomaly_model": {
    "type": "EnsembleAnomalyDetector",
    "estimators": ["IsolationForest", "OneClassSVM", "LOF"],
    "loaded": true
  },
  "feature_count": 25,
  "version": "1.0.0"
}
```

**Example**

```bash
curl http://localhost:8000/model/info
```

---

## Prediction Endpoints

### POST /predict

Predict threat for a single security event.

**Request Body**

```json
{
  "event": {
    "event_id": "evt-12345",
    "timestamp": "2025-01-15T14:30:22.123Z",
    "source_system": "zeek",
    "source_ip": "192.168.1.100",
    "destination_ip": "8.8.8.8",
    "source_port": 54321,
    "destination_port": 53,
    "protocol": "dns",
    "bytes_sent": 512,
    "bytes_received": 1024,
    "dns_query": "example.com"
  }
}
```

**Response**

```json
{
  "alert_id": "alert-67890",
  "timestamp": "2025-01-15T14:30:22.456Z",
  "event_id": "evt-12345",
  "is_threat": false,
  "threat_score": 0.23,
  "anomaly_score": 0.15,
  "severity": "low",
  "model_confidence": 0.89,
  "top_features": [
    {
      "name": "bytes_sent",
      "importance": 0.15,
      "value": 512
    },
    {
      "name": "destination_port",
      "importance": 0.12,
      "value": 53
    }
  ],
  "recommended_action": "monitor",
  "inference_time_ms": 45.2
}
```

**Field Descriptions**

| Field | Type | Description |
|-------|------|-------------|
| `alert_id` | string | Unique alert identifier |
| `timestamp` | string | Alert generation timestamp (ISO 8601) |
| `event_id` | string | Original event identifier |
| `is_threat` | boolean | True if classified as threat |
| `threat_score` | float | Threat probability (0.0-1.0) |
| `anomaly_score` | float | Anomaly score (0.0-1.0) |
| `severity` | string | Severity level: `low`, `medium`, `high`, `critical` |
| `model_confidence` | float | Model confidence (0.0-1.0) |
| `top_features` | array | Most important features for prediction |
| `recommended_action` | string | Suggested action: `allow`, `monitor`, `alert`, `block` |
| `inference_time_ms` | float | Inference time in milliseconds |

**Status Codes**
- `200` - Prediction successful
- `422` - Validation error (invalid event data)
- `503` - Service unavailable (models not loaded)

**Example**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "event_id": "evt-001",
      "source_system": "zeek",
      "source_ip": "192.168.1.100",
      "destination_ip": "8.8.8.8",
      "source_port": 54321,
      "destination_port": 53,
      "protocol": "dns",
      "bytes_sent": 512,
      "bytes_received": 1024
    }
  }'
```

**Python Example**

```python
import requests

event = {
    "event_id": "evt-001",
    "source_system": "zeek",
    "source_ip": "192.168.1.100",
    "destination_ip": "8.8.8.8",
    "source_port": 54321,
    "destination_port": 53,
    "protocol": "dns",
    "bytes_sent": 512,
    "bytes_received": 1024
}

response = requests.post(
    "http://localhost:8000/predict",
    json={"event": event}
)

result = response.json()
print(f"Threat: {result['is_threat']}")
print(f"Score: {result['threat_score']:.2f}")
print(f"Severity: {result['severity']}")
```

---

### POST /batch_predict

Predict threats for multiple events in a single request.

**Request Body**

Array of event objects:

```json
[
  {
    "event_id": "evt-001",
    "source_system": "zeek",
    "source_ip": "192.168.1.100",
    "destination_ip": "8.8.8.8",
    "source_port": 54321,
    "destination_port": 53,
    "protocol": "dns",
    "bytes_sent": 512,
    "bytes_received": 1024
  },
  {
    "event_id": "evt-002",
    "source_system": "zeek",
    "source_ip": "192.168.1.101",
    "destination_ip": "1.1.1.1",
    "source_port": 54322,
    "destination_port": 443,
    "protocol": "https",
    "bytes_sent": 2048,
    "bytes_received": 4096
  }
]
```

**Response**

```json
{
  "batch_id": "batch-12345",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "processing_time_ms": 89.5,
  "results": [
    {
      "alert_id": "alert-001",
      "event_id": "evt-001",
      "is_threat": false,
      "threat_score": 0.23,
      "severity": "low"
    },
    {
      "alert_id": "alert-002",
      "event_id": "evt-002",
      "is_threat": false,
      "threat_score": 0.18,
      "severity": "low"
    }
  ],
  "errors": []
}
```

**Limits**
- Maximum batch size: 100 events
- Recommended: 10-50 events per batch

**Example**

```bash
curl -X POST http://localhost:8000/batch_predict \
  -H "Content-Type: application/json" \
  -d '[
    {
      "event_id": "evt-001",
      "source_system": "zeek",
      "source_ip": "192.168.1.100",
      "destination_ip": "8.8.8.8",
      "source_port": 54321,
      "destination_port": 53,
      "protocol": "dns",
      "bytes_sent": 512,
      "bytes_received": 1024
    }
  ]'
```

---

## Metrics & Monitoring

### GET /metrics

Prometheus metrics endpoint for monitoring.

**Response** (Prometheus text format)

```
# HELP inference_latency_seconds Inference latency in seconds
# TYPE inference_latency_seconds histogram
inference_latency_seconds_bucket{le="0.01"} 45
inference_latency_seconds_bucket{le="0.05"} 120
inference_latency_seconds_bucket{le="0.1"} 180
inference_latency_seconds_sum 15.234
inference_latency_seconds_count 200

# HELP ai_detector_alerts_total Total number of alerts generated
# TYPE ai_detector_alerts_total counter
ai_detector_alerts_total{severity="low"} 150
ai_detector_alerts_total{severity="medium"} 35
ai_detector_alerts_total{severity="high"} 12
ai_detector_alerts_total{severity="critical"} 3

# HELP model_accuracy Current model accuracy
# TYPE model_accuracy gauge
model_accuracy 0.973
```

**Example**

```bash
curl http://localhost:8000/metrics
```

---

## Interactive Documentation

### GET /docs

OpenAPI (Swagger) interactive documentation.

Access at: `http://localhost:8000/docs`

Features:
- Try out API endpoints directly
- View request/response schemas
- Download OpenAPI specification

### GET /redoc

ReDoc alternative documentation interface.

Access at: `http://localhost:8000/redoc`

---

## Event Schemas

### Network Event

Required for network-based threat detection.

```json
{
  "event_id": "string (required)",
  "timestamp": "ISO 8601 datetime (optional, defaults to now)",
  "source_system": "string (required)",
  "source_ip": "IPv4 address (required)",
  "destination_ip": "IPv4 address (required)",
  "source_port": "integer 1-65535 (required)",
  "destination_port": "integer 1-65535 (required)",
  "protocol": "tcp|udp|dns|http|https (required)",
  "bytes_sent": "integer (optional)",
  "bytes_received": "integer (optional)",
  "packets_sent": "integer (optional)",
  "packets_received": "integer (optional)",
  "duration_ms": "integer (optional)",
  "flags": "string (optional, TCP flags)",
  "dns_query": "string (optional, for DNS)",
  "http_method": "string (optional, for HTTP/HTTPS)",
  "http_uri": "string (optional)",
  "http_status_code": "integer (optional)",
  "http_user_agent": "string (optional)"
}
```

### Endpoint Event

Required for endpoint-based threat detection.

```json
{
  "event_id": "string (required)",
  "timestamp": "ISO 8601 datetime (optional)",
  "source_system": "string (required)",
  "hostname": "string (required)",
  "username": "string (optional)",
  "process_name": "string (required)",
  "process_id": "integer (optional)",
  "command_line": "string (optional)",
  "parent_process": "string (optional)",
  "event_code": "integer (optional)"
}
```

### Application Log

Required for application log analysis.

```json
{
  "event_id": "string (required)",
  "timestamp": "ISO 8601 datetime (optional)",
  "source_system": "string (required)",
  "application_name": "string (required)",
  "log_level": "DEBUG|INFO|WARNING|ERROR|CRITICAL (required)",
  "message": "string (required)",
  "source_ip": "IPv4 address (optional)",
  "http_method": "string (optional)",
  "http_status_code": "integer (optional)",
  "response_time_ms": "float (optional)"
}
```

---

## Error Responses

### Validation Error (422)

```json
{
  "detail": [
    {
      "loc": ["body", "event", "source_ip"],
      "msg": "invalid IPv4 address",
      "type": "value_error.ipv4"
    }
  ]
}
```

### Service Unavailable (503)

```json
{
  "detail": "Models not loaded. Please train models first."
}
```

### Internal Server Error (500)

```json
{
  "detail": "Internal server error. Please try again later.",
  "error_id": "err-12345"
}
```

---

## Response Headers

All responses include:

```
Content-Type: application/json
X-Request-ID: <unique-request-id>
X-Inference-Time-MS: <inference-time>
```

---

## Best Practices

### 1. Batch When Possible

Use `/batch_predict` for multiple events:

```python
# Good: Batch request
response = requests.post("/batch_predict", json=events)

# Avoid: Individual requests in loop
for event in events:
    requests.post("/predict", json={"event": event})
```

### 2. Handle Errors Gracefully

```python
try:
    response = requests.post("/predict", json={"event": event}, timeout=5)
    response.raise_for_status()
    result = response.json()
except requests.exceptions.Timeout:
    # Handle timeout
    print("Request timed out")
except requests.exceptions.HTTPError as e:
    # Handle HTTP errors
    if e.response.status_code == 422:
        print(f"Validation error: {e.response.json()}")
    elif e.response.status_code == 503:
        print("Service unavailable")
```

### 3. Monitor Performance

Track key metrics:
- P95 latency < 100ms
- Error rate < 1%
- Throughput > 100 req/s

### 4. Use Connection Pooling

```python
import requests

# Create session for connection pooling
session = requests.Session()
session.mount('http://', requests.adapters.HTTPAdapter(pool_maxsize=10))

# Reuse session
response = session.post("/predict", json={"event": event})
```

### 5. Set Appropriate Timeouts

```python
# Set timeout for all requests
response = requests.post("/predict", json=data, timeout=5)

# Different timeouts for connect and read
response = requests.post("/predict", json=data, timeout=(3.0, 10.0))
```

---

## SDK Examples

### Python SDK

```python
class ThreatDetectorClient:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def predict(self, event: dict) -> dict:
        response = self.session.post(
            f"{self.base_url}/predict",
            json={"event": event},
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    def batch_predict(self, events: list) -> dict:
        response = self.session.post(
            f"{self.base_url}/batch_predict",
            json=events,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

# Usage
client = ThreatDetectorClient("http://localhost:8000")
result = client.predict(event)
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

class ThreatDetectorClient {
  constructor(baseURL, apiKey = null) {
    this.client = axios.create({
      baseURL,
      timeout: 5000,
      headers: apiKey ? { 'X-API-Key': apiKey } : {}
    });
  }

  async predict(event) {
    const response = await this.client.post('/predict', { event });
    return response.data;
  }

  async batchPredict(events) {
    const response = await this.client.post('/batch_predict', events);
    return response.data;
  }
}

// Usage
const client = new ThreatDetectorClient('http://localhost:8000');
const result = await client.predict(event);
```

### cURL Examples

```bash
# Single prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @event.json

# Batch prediction
curl -X POST http://localhost:8000/batch_predict \
  -H "Content-Type: application/json" \
  -d @events.json

# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics
```

---

## Changelog

### v1.0.0 (2025-01-15)
- Initial API release
- `/predict` endpoint for single predictions
- `/batch_predict` endpoint for batch predictions
- `/health` and `/ready` health check endpoints
- `/metrics` Prometheus metrics endpoint
- OpenAPI documentation at `/docs`

---

## Support

- **Documentation**: https://docs.threat-detector.example.com
- **API Status**: https://status.threat-detector.example.com
- **Support Email**: api-support@example.com
- **GitHub Issues**: https://github.com/your-org/threat-detector/issues

## License

Apache-2.0
