"""
FastAPI Inference Server
Real-time threat detection API with ML model serving
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from ..models.ensemble_model import EnsembleDetector
from ..models.anomaly_detector import AnomalyDetector
from ..feature_engineering.feature_extractor import FeatureExtractor, FeatureVector
from ..data_pipeline.schemas import NetworkEvent, Alert, Severity


# Configure logging
logger = structlog.get_logger(__name__)

# Prometheus metrics
ALERTS_TOTAL = Counter(
    'ai_detector_alerts_total',
    'Total number of alerts generated',
    ['severity']
)
INFERENCE_LATENCY = Histogram(
    'inference_latency_seconds',
    'Inference time in seconds',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
MODEL_ACCURACY = Gauge(
    'model_accuracy',
    'Current model accuracy'
)
REQUESTS_TOTAL = Counter(
    'inference_requests_total',
    'Total number of inference requests'
)


# FastAPI app
app = FastAPI(
    title="AI Threat Detection API",
    description="Real-time threat detection using ensemble ML models and anomaly detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class InferenceRequest(BaseModel):
    """Request model for threat detection"""
    event: NetworkEvent = Field(..., description="Security event to analyze")


class InferenceResponse(BaseModel):
    """Response model for threat detection"""
    alert_id: str
    timestamp: datetime
    is_threat: bool
    threat_score: float = Field(..., ge=0.0, le=1.0, description="ML model threat probability")
    anomaly_score: float = Field(..., description="Anomaly detection score")
    severity: Severity
    model_confidence: float = Field(..., ge=0.0, le=1.0)
    top_features: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_action: str
    inference_time_ms: float
    model_details: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "alert-12847",
                "timestamp": "2025-11-15T21:45:00Z",
                "is_threat": True,
                "threat_score": 0.92,
                "anomaly_score": 2.34,
                "severity": "high",
                "model_confidence": 0.89,
                "top_features": [
                    {"feature": "unique_dst_ports_week", "value": 47, "contribution": 0.31}
                ],
                "recommended_action": "Isolate host, investigate recent activity",
                "inference_time_ms": 87.5,
                "model_details": {
                    "ensemble_prediction": 1,
                    "anomaly_prediction": -1
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    models_loaded: bool
    redis_connected: bool
    timestamp: datetime


# Global state
class AppState:
    """Application state container"""
    def __init__(self):
        self.ensemble_detector: Optional[EnsembleDetector] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None
        self.feature_extractor: Optional[FeatureExtractor] = None
        self.models_loaded = False


state = AppState()


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    logger.info("starting_inference_server")

    try:
        # Initialize feature extractor
        state.feature_extractor = FeatureExtractor()
        logger.info("feature_extractor_initialized")

        # Try to load pre-trained models
        ensemble_path = Path("models/ensemble")
        anomaly_path = Path("models/anomaly")

        if ensemble_path.exists():
            state.ensemble_detector = EnsembleDetector(model_path=ensemble_path)
            logger.info("ensemble_model_loaded", path=str(ensemble_path))
        else:
            # Initialize without pre-trained models (for demo)
            state.ensemble_detector = EnsembleDetector()
            logger.warning("ensemble_model_not_found_using_untrained")

        if anomaly_path.exists():
            state.anomaly_detector = AnomalyDetector(model_path=anomaly_path)
            logger.info("anomaly_model_loaded", path=str(anomaly_path))
        else:
            state.anomaly_detector = AnomalyDetector()
            logger.warning("anomaly_model_not_found_using_untrained")

        state.models_loaded = True
        logger.info("inference_server_ready")

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        state.models_loaded = False


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("shutting_down_inference_server")

    if state.feature_extractor:
        state.feature_extractor.close()

    logger.info("inference_server_shutdown_complete")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return {
        "service": "AI Threat Detection API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns service health status and model readiness
    """
    redis_connected = False
    try:
        if state.feature_extractor and state.feature_extractor.redis:
            state.feature_extractor.redis.ping()
            redis_connected = True
    except Exception as e:
        logger.warning("redis_health_check_failed", error=str(e))

    return HealthResponse(
        status="healthy" if state.models_loaded else "degraded",
        models_loaded=state.models_loaded,
        redis_connected=redis_connected,
        timestamp=datetime.utcnow()
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check for Kubernetes

    Returns 200 if ready to serve requests, 503 otherwise
    """
    if state.models_loaded:
        return {"ready": True}
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded"
        )


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """
    Prometheus metrics endpoint

    Exposes metrics for monitoring and alerting
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=InferenceResponse, tags=["Inference"])
async def predict_threat(request: InferenceRequest):
    """
    Predict threat from security event

    Analyzes network event using ensemble ML models and anomaly detection.
    Returns threat classification with explainability features.

    Args:
        request: InferenceRequest containing security event

    Returns:
        InferenceResponse with threat analysis
    """
    start_time = time.time()
    REQUESTS_TOTAL.inc()

    if not state.models_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded. Please wait for initialization."
        )

    try:
        event = request.event

        # Extract features
        features = state.feature_extractor.extract_from_network_event(event)
        feature_array = features.to_numpy_array()

        # Ensemble model prediction
        if state.ensemble_detector.is_trained:
            ensemble_pred, threat_prob, ensemble_confidence = \
                state.ensemble_detector.predict_single(feature_array)
        else:
            # If not trained, use random prediction for demo
            ensemble_pred = 0
            threat_prob = 0.1
            ensemble_confidence = 0.5

        # Anomaly detection
        if state.anomaly_detector.is_trained:
            anomaly_pred, anomaly_score, anomaly_scores = \
                state.anomaly_detector.predict_single(feature_array)
        else:
            anomaly_pred = 1  # Normal
            anomaly_score = 0.0
            anomaly_scores = {}

        # Determine if threat (either ensemble or anomaly flags it)
        is_threat = (ensemble_pred == 1) or (anomaly_pred == -1)

        # Calculate severity
        if threat_prob > 0.9 or anomaly_score > 3.0:
            severity = Severity.CRITICAL
        elif threat_prob > 0.75 or anomaly_score > 2.0:
            severity = Severity.HIGH
        elif threat_prob > 0.5 or anomaly_score > 1.0:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        # Generate top features (simplified - in production would use SHAP)
        top_features = [
            {
                "feature": "conn_count_1min",
                "value": float(features.conn_count_1min),
                "contribution": 0.25
            },
            {
                "feature": "unique_dst_ports_1min",
                "value": float(features.unique_dst_ports_1min),
                "contribution": 0.20
            },
            {
                "feature": "payload_entropy",
                "value": float(features.payload_entropy),
                "contribution": 0.18
            }
        ]

        # Recommended action
        if severity in [Severity.CRITICAL, Severity.HIGH]:
            recommended_action = "Isolate host immediately, investigate payload, check for lateral movement"
        elif severity == Severity.MEDIUM:
            recommended_action = "Monitor closely, investigate if pattern continues"
        else:
            recommended_action = "Log for future analysis"

        # Calculate inference time
        inference_time_ms = (time.time() - start_time) * 1000

        # Record metrics
        ALERTS_TOTAL.labels(severity=severity.value).inc()
        INFERENCE_LATENCY.observe(time.time() - start_time)

        # Generate alert ID
        alert_id = f"alert-{int(time.time() * 1000)}"

        # Log detection
        logger.info(
            "threat_detection_completed",
            alert_id=alert_id,
            source_ip=event.source_ip,
            is_threat=is_threat,
            threat_score=threat_prob,
            anomaly_score=anomaly_score,
            severity=severity.value,
            inference_time_ms=inference_time_ms
        )

        return InferenceResponse(
            alert_id=alert_id,
            timestamp=datetime.utcnow(),
            is_threat=is_threat,
            threat_score=threat_prob,
            anomaly_score=anomaly_score,
            severity=severity,
            model_confidence=ensemble_confidence,
            top_features=top_features,
            recommended_action=recommended_action,
            inference_time_ms=inference_time_ms,
            model_details={
                "ensemble_prediction": int(ensemble_pred),
                "anomaly_prediction": int(anomaly_pred),
                "anomaly_model_scores": anomaly_scores
            }
        )

    except Exception as e:
        logger.error("inference_failed", error=str(e), event_id=event.event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {str(e)}"
        )


@app.post("/batch_predict", tags=["Inference"])
async def batch_predict(events: List[NetworkEvent]):
    """
    Batch prediction for multiple events

    Args:
        events: List of network events

    Returns:
        List of inference responses
    """
    results = []

    for event in events:
        try:
            request = InferenceRequest(event=event)
            response = await predict_threat(request)
            results.append(response)
        except Exception as e:
            logger.error("batch_prediction_item_failed", event_id=event.event_id, error=str(e))
            continue

    return {
        "total": len(events),
        "successful": len(results),
        "failed": len(events) - len(results),
        "results": results
    }


@app.get("/model/info", tags=["Model Management"])
async def model_info():
    """
    Get information about loaded models

    Returns model metadata and performance statistics
    """
    return {
        "ensemble_model": {
            "is_trained": state.ensemble_detector.is_trained if state.ensemble_detector else False,
            "weights": state.ensemble_detector.weights if state.ensemble_detector else None
        },
        "anomaly_model": {
            "is_trained": state.anomaly_detector.is_trained if state.anomaly_detector else False,
            "contamination": state.anomaly_detector.contamination if state.anomaly_detector else None
        },
        "feature_count": 25,
        "models_loaded": state.models_loaded
    }


# Example usage
if __name__ == "__main__":
    import uvicorn

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Run server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
