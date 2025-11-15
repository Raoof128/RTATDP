# Real-Time AI Threat Detection Pipeline - System Architecture

## Document Information

**Version:** 1.0
**Last Updated:** 2025-11-15
**Author:** AI Security Engineering Team
**Status:** Design Approved

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Core Components](#core-components)
4. [Data Flow Architecture](#data-flow-architecture)
5. [ML Pipeline Architecture](#ml-pipeline-architecture)
6. [Technical Specifications](#technical-specifications)
7. [Integration Architecture](#integration-architecture)
8. [Deployment Topology](#deployment-topology)
9. [Security & Compliance](#security--compliance)
10. [Scalability & Performance](#scalability--performance)
11. [Disaster Recovery](#disaster-recovery)

---

## Executive Summary

This document describes the architecture of a real-time AI-powered threat detection system designed to process 500K+ security events per second with sub-100ms latency. The system combines supervised ML models (ensemble of Random Forest, XGBoost, LightGBM) with unsupervised anomaly detection (Isolation Forest, One-Class SVM, LOF) to achieve >95% true positive rates while maintaining <2% false positive rates.

### Key Architectural Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| **Kafka for Event Streaming** | Industry-standard, high-throughput, fault-tolerant | Operational complexity vs alternatives like RabbitMQ |
| **Apache Flink for Stream Processing** | Low-latency windowing, exactly-once semantics | Learning curve vs Kafka Streams |
| **FastAPI for Inference Server** | High performance, async support, auto-documentation | Python GIL limitations (mitigated via uvicorn workers) |
| **Redis for Feature Store** | In-memory speed, pub/sub capabilities | Persistence trade-offs vs PostgreSQL |
| **Ensemble ML Models** | Reduced variance, improved robustness | Increased inference complexity |
| **Kubernetes Deployment** | Cloud-agnostic, auto-scaling, self-healing | Infrastructure overhead vs VM-based deployment |

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA INGESTION LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│  Network Sources  │  Endpoint Sources  │  Application Sources  │  APIs  │
│  - Zeek DNS/HTTP  │  - Sysmon Events   │  - Web Server Logs   │ - CTI  │
│  - Suricata IDS   │  - osquery         │  - Auth Logs         │ - MISP │
│  - NetFlow/IPFIX  │  - EDR Alerts      │  - Database Logs     │        │
└──────────┬──────────────────┬────────────────────┬──────────────────┬───┘
           │                  │                    │                  │
           ▼                  ▼                    ▼                  ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                   KAFKA EVENT STREAMING                          │
    │  Topics: network_events, endpoint_events, app_logs, threat_intel│
    └──────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │              APACHE FLINK STREAM PROCESSING                      │
    │  - Feature Aggregation (1m, 5m, 1h windows)                     │
    │  - Event Enrichment (GeoIP, Reputation)                         │
    │  - Stateful Computations (session tracking)                     │
    └──────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                    REDIS FEATURE STORE                           │
    │  - Real-time Feature Cache (TTL-based)                          │
    │  - Session State Management                                      │
    │  - Rate Limiting & Deduplication                                │
    └──────────────────────┬───────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
    ┌─────────────────┐           ┌──────────────────┐
    │  ML INFERENCE   │           │  SIGNATURE RULES │
    │  FastAPI Server │           │  Sigma/YARA      │
    │  - Ensemble     │           │  - MITRE ATT&CK  │
    │  - Anomaly Det. │           │  - Custom Rules  │
    └────────┬────────┘           └────────┬─────────┘
             │                             │
             └──────────┬──────────────────┘
                        │
                        ▼
             ┌────────────────────────┐
             │  ALERT CORRELATION &   │
             │  DEDUPLICATION ENGINE  │
             └────────┬───────────────┘
                      │
                      ▼
             ┌────────────────────────┐
             │  ALERT ENRICHMENT &    │
             │  THREAT INTELLIGENCE   │
             └────────┬───────────────┘
                      │
                      ▼
       ┌──────────────┴──────────────────┐
       │                                 │
       ▼                                 ▼
┌────────────┐                    ┌─────────────┐
│    SIEM    │                    │ SOAR/ITSM   │
│  - Splunk  │                    │ - TheHive   │
│  - Elastic │                    │ - JIRA      │
│  - Sentinel│                    │ - PagerDuty │
└────────────┘                    └─────────────┘
```

### Component Interaction Flow

1. **Event Ingestion**: Multiple sources publish events to Kafka topics (partitioned by source type)
2. **Stream Processing**: Flink consumes events, performs windowed aggregations, enrichment
3. **Feature Storage**: Computed features cached in Redis with TTL-based expiration
4. **Parallel Detection**:
   - ML models score events using cached features
   - Signature rules evaluate for known patterns
5. **Alert Management**: Correlation engine groups related alerts, removes duplicates
6. **Integration**: Enriched alerts exported to SIEM/SOAR platforms

---

## Core Components

### 1. Data Ingestion Layer

**Purpose**: Collect security events from heterogeneous sources and normalize into Kafka topics

**Technologies**:
- **Kafka Connect**: Pre-built connectors for Syslog, file tails, databases
- **Filebeat/Logstash**: Log shipping agents
- **Custom Python Producers**: API integrations (EDR, CTI feeds)

**Data Sources**:

| Category | Source | Format | Volume | Latency Requirement |
|----------|--------|--------|--------|---------------------|
| Network | Zeek DNS | JSON | 50K events/sec | <1s |
| Network | Zeek HTTP | JSON | 30K events/sec | <1s |
| Network | Suricata Alerts | Eve JSON | 5K events/sec | <500ms |
| Network | NetFlow | IPFIX | 100K flows/sec | <2s |
| Endpoint | Sysmon | Windows Event Log | 80K events/sec | <1s |
| Endpoint | osquery | JSON | 20K events/sec | <2s |
| Application | Web Logs | Apache Combined | 150K events/sec | <5s |
| Threat Intel | MISP Feeds | STIX 2.0 | 1K IOCs/hour | <1min |

**Schema Validation**:
```python
# Avro schema example for network events
NETWORK_EVENT_SCHEMA = {
    "type": "record",
    "name": "NetworkEvent",
    "fields": [
        {"name": "timestamp", "type": "long"},
        {"name": "source_ip", "type": "string"},
        {"name": "destination_ip", "type": "string"},
        {"name": "source_port", "type": "int"},
        {"name": "destination_port", "type": "int"},
        {"name": "protocol", "type": "string"},
        {"name": "bytes_sent", "type": "long"},
        {"name": "bytes_received", "type": "long"},
        {"name": "flags", "type": ["null", "string"], "default": null}
    ]
}
```

### 2. Feature Engineering Pipeline

**Purpose**: Transform raw events into ML-ready features using temporal aggregations

**Technologies**:
- **Apache Flink**: Stateful stream processing
- **Flink SQL**: Declarative window functions
- **Custom UDFs**: Complex feature extraction (entropy, statistical moments)

**Feature Categories**:

#### Temporal Features (Time Windows: 1min, 5min, 1hour)
```sql
-- Example Flink SQL for connection count aggregation
SELECT
    source_ip,
    TUMBLE_END(event_time, INTERVAL '1' MINUTE) as window_end,
    COUNT(*) as connection_count_1min,
    COUNT(DISTINCT destination_ip) as unique_dst_ips_1min,
    COUNT(DISTINCT destination_port) as unique_dst_ports_1min,
    AVG(bytes_sent) as avg_bytes_sent_1min,
    STDDEV(bytes_sent) as stddev_bytes_sent_1min
FROM network_events
GROUP BY source_ip, TUMBLE(event_time, INTERVAL '1' MINUTE)
```

#### Statistical Features
- **Entropy Calculations**: DNS domain entropy, HTTP User-Agent entropy
- **Distribution Metrics**: Payload size percentiles (P50, P90, P99)
- **Frequency Analysis**: Request rate per source/destination pair

#### Behavioral Features
- **Novelty Detection**: Never-before-seen port combinations
- **Geographic Anomalies**: Connections from new countries
- **Time-based Patterns**: Off-hours activity detection
- **Peer Comparison**: Deviation from similar asset groups

#### Threat Intelligence Features
- **Reputation Scores**: IP/Domain/Hash lookups (VirusTotal, AbuseIPDB)
- **MITRE ATT&CK Tags**: Technique/Tactic mapping
- **IOC Matches**: Known malicious indicators

**Feature Store Schema**:
```python
FEATURE_VECTOR = {
    "source_ip": "string",
    "timestamp": "timestamp",

    # Temporal aggregations
    "conn_count_1min": "int",
    "conn_count_5min": "int",
    "conn_count_1hour": "int",
    "unique_dst_ports_1min": "int",
    "unique_dst_ports_5min": "int",

    # Statistical
    "payload_size_mean": "float",
    "payload_size_stddev": "float",
    "dns_entropy": "float",
    "http_ua_entropy": "float",

    # Behavioral
    "is_novel_port": "bool",
    "is_new_country": "bool",
    "off_hours_activity": "bool",
    "peer_deviation_score": "float",

    # Threat Intelligence
    "ip_reputation_score": "int",  # -100 (malicious) to 100 (benign)
    "mitre_technique": "string[]",
    "ioc_matches": "int"
}
```

### 3. Detection Engine

**Purpose**: Parallel processing of ML-based and signature-based threat detection

#### ML Inference Server (FastAPI)

**Architecture**:
```python
# FastAPI application structure
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import numpy as np
import joblib

app = FastAPI(title="Threat Detection Inference API")

# Load models at startup
@app.on_event("startup")
async def load_models():
    app.state.rf_model = joblib.load("models/random_forest.pkl")
    app.state.xgb_model = joblib.load("models/xgboost.pkl")
    app.state.lgb_model = joblib.load("models/lightgbm.pkl")
    app.state.isolation_forest = joblib.load("models/isolation_forest.pkl")

class InferenceRequest(BaseModel):
    features: List[float]
    event_metadata: dict

@app.post("/predict")
async def predict_threat(request: InferenceRequest):
    # Ensemble prediction
    rf_score = app.state.rf_model.predict_proba([request.features])[0][1]
    xgb_score = app.state.xgb_model.predict_proba([request.features])[0][1]
    lgb_score = app.state.lgb_model.predict_proba([request.features])[0][1]

    # Weighted ensemble (soft voting)
    ensemble_score = (0.4 * rf_score + 0.35 * xgb_score + 0.25 * lgb_score)

    # Anomaly detection
    anomaly_score = app.state.isolation_forest.decision_function([request.features])[0]

    return {
        "threat_score": float(ensemble_score),
        "anomaly_score": float(anomaly_score),
        "is_threat": ensemble_score > 0.85,
        "confidence": max(rf_score, xgb_score, lgb_score)
    }
```

**Performance Optimizations**:
- **Batch Inference**: Accumulate 64-256 requests before processing
- **Model Caching**: Keep models in memory (no disk I/O per request)
- **Async Processing**: Non-blocking I/O for feature store lookups
- **Connection Pooling**: Reuse Redis connections

#### Signature-Based Detection

**Rule Formats**:
- **Sigma Rules**: Generic SIEM rules (converted to platform-specific queries)
- **YARA Rules**: Pattern matching for malware signatures
- **Custom Rules**: Python-based detection logic

**Example Sigma Rule**:
```yaml
title: Suspicious PowerShell Download Cradle
id: 85b0b087-eddf-4a2b-b033-d771fa2b9775
description: Detects PowerShell download cradles used by attackers
status: experimental
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\powershell.exe'
        CommandLine|contains:
            - 'IEX'
            - 'Invoke-Expression'
            - 'DownloadString'
            - 'DownloadFile'
    condition: selection
falsepositives:
    - Legitimate admin scripts
level: high
tags:
    - attack.execution
    - attack.t1059.001
```

### 4. Alert Correlation & Deduplication

**Purpose**: Reduce alert fatigue by grouping related events and removing duplicates

**Strategies**:

1. **Time-Window Deduplication** (60-second default):
   ```python
   def is_duplicate(new_alert, existing_alerts, window_seconds=60):
       for existing in existing_alerts:
           if (new_alert.timestamp - existing.timestamp) < window_seconds:
               if (new_alert.source_ip == existing.source_ip and
                   new_alert.threat_type == existing.threat_type):
                   return True
       return False
   ```

2. **Multi-Stage Correlation**:
   - **Spatial**: Group alerts from same source/destination
   - **Temporal**: Detect attack chains (e.g., recon → exploitation → lateral movement)
   - **Tactical**: Map to MITRE ATT&CK kill chain

3. **Alert Prioritization**:
   ```python
   def calculate_priority(alert):
       score = 0

       # Threat score contribution
       score += alert.threat_score * 40

       # Asset criticality
       if alert.target_asset in CRITICAL_ASSETS:
           score += 30

       # Threat intelligence
       if alert.ioc_matches > 0:
           score += 20

       # Multi-technique chain
       if alert.mitre_techniques_count > 2:
           score += 10

       return score  # 0-100 scale
   ```

### 5. Orchestration Layer (Apache Airflow)

**Purpose**: Manage ML training, model deployment, and batch processing workflows

**DAGs**:

1. **Model Training DAG** (Daily at 2 AM):
   - Extract training data from data warehouse
   - Feature engineering
   - Train ensemble models
   - Evaluate performance
   - Register model if improved
   - Deploy via canary release

2. **Drift Detection DAG** (Hourly):
   - Monitor feature distributions
   - Calculate KL divergence from baseline
   - Alert if drift detected
   - Trigger retraining if threshold exceeded

3. **Threat Intelligence Update DAG** (Every 15 minutes):
   - Fetch IOCs from MISP, VirusTotal
   - Update Redis reputation cache
   - Refresh YARA/Sigma rules

---

## Data Flow Architecture

### Event Processing Flow

```
[1] Raw Event Arrival (Kafka Producer)
     │
     ├─> Kafka Topic Partition (based on source_ip hash)
     │
[2] Flink Consumer Reads Event
     │
     ├─> Schema Validation (Avro deserializer)
     │
[3] Feature Extraction (Flink UDF)
     │
     ├─> Window Aggregations (1min, 5min, 1hour)
     ├─> Stateful Lookups (has IP been seen before?)
     ├─> External Enrichment (GeoIP, Reputation)
     │
[4] Feature Store Write (Redis)
     │
     ├─> Key: source_ip:timestamp:feature_name
     ├─> TTL: 1 hour (auto-expire old features)
     │
[5] Detection Trigger
     │
     ├─> FastAPI /predict endpoint called
     ├─> Feature vector retrieved from Redis
     │
[6] Parallel Detection
     │
     ├─> ML Models (ensemble + anomaly)
     ├─> Signature Rules (Sigma/YARA)
     │
[7] Alert Generation (if threat detected)
     │
     ├─> Alert ID generated
     ├─> SHAP values calculated
     ├─> Threat intelligence enrichment
     │
[8] Correlation & Deduplication
     │
     ├─> Check for duplicates in 60s window
     ├─> Group related alerts
     ├─> Calculate priority score
     │
[9] Alert Export
     │
     ├─> Splunk HEC
     ├─> TheHive case creation
     ├─> MISP IOC sharing
     └─> Email/PagerDuty (critical alerts)
```

### Data Retention

| Data Type | Storage System | Retention Period | Rationale |
|-----------|----------------|------------------|-----------|
| Raw Events | Kafka | 7 days | Replay capability, forensics |
| Aggregated Features | Redis | 1 hour | Real-time inference only |
| Alerts | PostgreSQL | 90 days | Compliance, trend analysis |
| Model Artifacts | S3/MinIO | 1 year | Versioning, rollback |
| Logs (application) | Elasticsearch | 30 days | Debugging, auditing |
| Metrics | Prometheus | 15 days | Performance monitoring |

---

## ML Pipeline Architecture

### Training Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                   TRAINING DATA SOURCES                     │
│  - Historical Incidents (labeled by SOC analysts)          │
│  - Red Team Simulations (known attacks)                    │
│  - Public Datasets (CICIDS2017, NSL-KDD, UNSW-NB15)       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  DATA PREPROCESSING  │
          │  - Class Balancing   │
          │  - Feature Scaling   │
          │  - Train/Val Split   │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  FEATURE ENGINEERING │
          │  (same as inference) │
          └──────────┬───────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
           ▼                   ▼
    ┌─────────────┐    ┌──────────────┐
    │ SUPERVISED  │    │ UNSUPERVISED │
    │  TRAINING   │    │   TRAINING   │
    │ - RF        │    │ - Iso Forest │
    │ - XGBoost   │    │ - One-Class  │
    │ - LightGBM  │    │   SVM        │
    └──────┬──────┘    └──────┬───────┘
           │                  │
           └────────┬─────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  MODEL EVALUATION   │
         │  - AUC-ROC          │
         │  - Precision/Recall │
         │  - F1 Score         │
         │  - Confusion Matrix │
         └──────────┬──────────┘
                    │
                    ▼
              ┌──────────┐
              │ AUC-ROC  │ No
              │  > 0.95? ├────> Hyperparameter Tuning
              └────┬─────┘
                   │ Yes
                   ▼
         ┌──────────────────┐
         │ MODEL REGISTRY   │
         │ - Version Tag    │
         │ - Metadata       │
         │ - Performance    │
         └────────┬─────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ CANARY DEPLOY   │
         │ 10% traffic ->  │
         │ Monitor 24h     │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ FULL DEPLOYMENT │
         └─────────────────┘
```

### Model Performance Monitoring

**Metrics Tracked**:
- **Accuracy Metrics**: Precision, Recall, F1-score, AUC-ROC
- **Latency Metrics**: Inference time (P50, P95, P99)
- **Data Quality**: Feature null rates, distribution shifts
- **Business Metrics**: MTTR, false positive rate, analyst feedback

**Drift Detection**:
```python
def detect_feature_drift(current_dist, baseline_dist, threshold=0.1):
    """
    Detect if feature distribution has drifted using KL divergence
    """
    from scipy.stats import entropy

    kl_div = entropy(current_dist, baseline_dist)

    if kl_div > threshold:
        alert(f"Feature drift detected: KL divergence = {kl_div:.4f}")
        trigger_retraining()

    return kl_div
```

---

## Technical Specifications

### Performance Requirements

| Metric | Target | Measurement Method | SLA |
|--------|--------|-------------------|-----|
| **Throughput** | 500K events/sec | Kafka consumer lag | 99th percentile |
| **Latency (Ingestion to Alert)** | <500ms | Distributed tracing | 95th percentile |
| **Inference Latency** | <100ms | API response time | 95th percentile |
| **Detection Accuracy** | >95% TP rate | Confusion matrix on test set | Monthly evaluation |
| **False Positive Rate** | <2% | FP / (FP + TN) | Weekly review |
| **Availability** | 99.9% | Uptime monitoring | Monthly |
| **Model Explainability** | SHAP values for all alerts | Coverage metric | 100% |

### Resource Requirements

**Production Deployment (AWS/GCP)**:

| Component | Instance Type | Count | CPU | Memory | Storage |
|-----------|---------------|-------|-----|--------|---------|
| Kafka Brokers | m5.2xlarge | 3 | 8 vCPU | 32 GB | 1 TB SSD |
| Zookeeper | t3.medium | 3 | 2 vCPU | 4 GB | 50 GB |
| Flink Task Managers | c5.4xlarge | 5 | 16 vCPU | 32 GB | 200 GB |
| Redis Cluster | r5.2xlarge | 3 | 8 vCPU | 64 GB | - |
| Inference Servers | c5.2xlarge | 5-10 (HPA) | 8 vCPU | 16 GB | 50 GB |
| PostgreSQL (Alerts DB) | r5.xlarge | 1 | 4 vCPU | 32 GB | 500 GB |
| Airflow | t3.large | 1 | 2 vCPU | 8 GB | 100 GB |

**Estimated Monthly Cost**: ~$8,000 USD (AWS us-east-1)

### Scalability Characteristics

**Horizontal Scaling**:
- **Kafka**: Add brokers, increase partitions
- **Flink**: Add task managers (parallelism)
- **Inference Servers**: Kubernetes HPA (2-10 pods based on latency)
- **Redis**: Cluster mode with additional master/replica pairs

**Vertical Scaling**:
- **Redis**: Increase memory for larger feature cache
- **PostgreSQL**: Upgrade instance for alert database

---

## Integration Architecture

### SIEM Integration

**Splunk HTTP Event Collector**:
```python
class SplunkExporter:
    def __init__(self, hec_url, hec_token):
        self.hec_url = hec_url
        self.headers = {
            'Authorization': f'Splunk {hec_token}',
            'Content-Type': 'application/json'
        }

    def export_alert(self, alert):
        payload = {
            'event': alert.to_dict(),
            'source': 'ai_threat_detector',
            'sourcetype': '_json',
            'index': 'security',
            'time': alert.timestamp
        }

        response = requests.post(
            self.hec_url,
            json=payload,
            headers=self.headers,
            timeout=5
        )

        response.raise_for_status()
```

**Elastic Common Schema (ECS)**:
```json
{
  "@timestamp": "2025-11-15T21:45:00.000Z",
  "event": {
    "kind": "alert",
    "category": ["intrusion_detection"],
    "type": ["indicator"],
    "severity": 8,
    "risk_score": 92
  },
  "threat": {
    "framework": "MITRE ATT&CK",
    "tactic": {
      "name": ["Execution"],
      "id": ["TA0002"]
    },
    "technique": {
      "name": ["PowerShell"],
      "id": ["T1059.001"]
    }
  },
  "source": {
    "ip": "192.168.1.100",
    "geo": {
      "country_name": "United States"
    }
  },
  "ai_detector": {
    "threat_score": 0.92,
    "model_confidence": 0.89,
    "top_features": [...]
  }
}
```

### SOAR Integration

**TheHive Case Creation**:
```python
from thehive4py.api import TheHiveApi
from thehive4py.models import Case, CaseTask

def create_thehive_case(alert):
    api = TheHiveApi(
        url=os.getenv('THEHIVE_URL'),
        apikey=os.getenv('THEHIVE_API_KEY')
    )

    case = Case(
        title=f"AI Detected Threat: {alert.threat_type}",
        description=f"""
        **Threat Score**: {alert.threat_score}
        **Source IP**: {alert.source_ip}
        **Top Contributing Features**:
        {alert.shap_explanation}

        **Recommended Actions**:
        - Isolate host {alert.source_ip}
        - Investigate recent activity
        - Check for lateral movement
        """,
        severity=2 if alert.threat_score > 0.9 else 1,
        tlp=2,  # TLP:AMBER
        tags=['ai_detection', alert.mitre_technique]
    )

    response = api.create_case(case)
    return response.json()['id']
```

---

## Deployment Topology

### Local Development

```yaml
# docker-compose.yml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  inference-server:
    build: ./src/inference_server
    ports: ["8000:8000"]
    depends_on: [redis]
    environment:
      REDIS_URL: redis://redis:6379
```

### Production (Kubernetes)

```yaml
# k8s/inference-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: threat-detector-inference
  namespace: security
spec:
  replicas: 5
  selector:
    matchLabels:
      app: threat-detector
      component: inference
  template:
    metadata:
      labels:
        app: threat-detector
        component: inference
    spec:
      containers:
      - name: inference-server
        image: threat-detector:v1.0.0
        ports:
        - containerPort: 8000
        resources:
          requests:
            cpu: 2000m
            memory: 4Gi
          limits:
            cpu: 4000m
            memory: 8Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: threat-detector-hpa
  namespace: security
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: threat-detector-inference
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Pods
    pods:
      metric:
        name: inference_latency_p95
      target:
        type: AverageValue
        averageValue: 100m  # 100ms
```

---

## Security & Compliance

### Security Measures

1. **Authentication & Authorization**:
   - API authentication via JWT tokens
   - RBAC for Kubernetes resources
   - Network policies for pod-to-pod communication

2. **Data Protection**:
   - TLS 1.3 for all inter-service communication
   - Encryption at rest for PostgreSQL
   - PII redaction in logs

3. **Secrets Management**:
   - Kubernetes Secrets for credentials
   - HashiCorp Vault for production secrets
   - Regular rotation of API keys

4. **Compliance**:
   - GDPR: 90-day alert retention, data deletion procedures
   - SOC 2: Audit logging, access controls
   - NIST CSF: Aligned detection capabilities

---

## Disaster Recovery

### Backup Strategy

| Component | Backup Frequency | Retention | RTO | RPO |
|-----------|------------------|-----------|-----|-----|
| ML Models | After each training | 1 year | 5 min | N/A |
| Alert Database | Hourly | 90 days | 15 min | 1 hour |
| Configuration | On change | 1 year | 5 min | N/A |
| Kafka Topics | Continuous (replication) | 7 days | 10 min | 1 min |

### Failover Procedures

1. **Inference Server Failure**:
   - K8s automatically restarts pod
   - HPA scales up if needed
   - Fallback to signature-only detection

2. **Kafka Broker Failure**:
   - ISR (In-Sync Replicas) continue serving
   - Automatic leader election
   - No data loss (min.insync.replicas=2)

3. **Redis Failure**:
   - Sentinel promotes replica to master
   - Feature recomputation for missed data
   - <5 minute recovery

4. **Complete Datacenter Failure**:
   - Multi-region deployment (active-passive)
   - DNS failover to backup region
   - <15 minute RTO

---

## Conclusion

This architecture provides a production-grade, scalable, and maintainable foundation for real-time AI threat detection. The design prioritizes:

- **Performance**: Sub-100ms inference, 500K+ events/sec throughput
- **Accuracy**: >95% true positive rate, <2% false positives
- **Explainability**: SHAP values for all alerts
- **Operational Excellence**: Monitoring, alerting, disaster recovery
- **Integration**: Seamless SIEM/SOAR connectivity

**Next Steps**:
1. Implement data pipeline (Phase 2)
2. Train initial ML models (Phase 3)
3. Deploy inference server (Phase 4)
4. Integration testing (Phase 5)
5. Production rollout (Phase 6)

---

**Document Version Control**:
- v1.0 (2025-11-15): Initial architecture design
