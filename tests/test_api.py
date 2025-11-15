"""
Unit tests for FastAPI inference server
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from unittest.mock import Mock, patch

from src.inference_server.api import app
from src.data_pipeline.schemas import NetworkEvent, Protocol


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_event():
    """Create sample network event"""
    return NetworkEvent(
        event_id="test-123",
        source_system="zeek",
        source_ip="192.168.1.100",
        destination_ip="8.8.8.8",
        source_port=54321,
        destination_port=53,
        protocol=Protocol.DNS,
        bytes_sent=512,
        bytes_received=1024
    )


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AI Threat Detection API"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "models_loaded" in data
        assert "timestamp" in data

    def test_ready_endpoint_when_not_ready(self, client):
        """Test readiness endpoint when models not loaded"""
        # Models won't be loaded in test environment
        response = client.get("/ready")
        # Should return 503 if models not loaded
        assert response.status_code in [200, 503]

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Check for Prometheus format
        assert b"# HELP" in response.content or b"# TYPE" in response.content


class TestModelInfoEndpoint:
    """Test model information endpoint"""

    def test_model_info(self, client):
        """Test model info endpoint"""
        response = client.get("/model/info")
        assert response.status_code == 200
        data = response.json()
        assert "ensemble_model" in data
        assert "anomaly_model" in data
        assert "feature_count" in data
        assert data["feature_count"] == 25


class TestInferenceEndpoint:
    """Test prediction endpoints"""

    def test_predict_endpoint_structure(self, client, sample_event):
        """Test predict endpoint returns correct structure"""
        response = client.post(
            "/predict",
            json={"event": sample_event.model_dump(mode='json')}
        )

        # May fail if models not loaded, but should have correct error format
        if response.status_code == 200:
            data = response.json()
            assert "alert_id" in data
            assert "timestamp" in data
            assert "is_threat" in data
            assert "threat_score" in data
            assert "anomaly_score" in data
            assert "severity" in data
            assert "model_confidence" in data
            assert "top_features" in data
            assert "recommended_action" in data
            assert "inference_time_ms" in data
        elif response.status_code == 503:
            # Models not loaded
            data = response.json()
            assert "detail" in data

    def test_predict_invalid_event(self, client):
        """Test predict with invalid event data"""
        response = client.post(
            "/predict",
            json={"event": {"invalid": "data"}}
        )
        assert response.status_code == 422  # Validation error

    def test_predict_missing_required_fields(self, client):
        """Test predict with missing required fields"""
        response = client.post(
            "/predict",
            json={"event": {
                "event_id": "test",
                "source_system": "test",
                # Missing required IP and port fields
            }}
        )
        assert response.status_code == 422


class TestBatchPrediction:
    """Test batch prediction endpoint"""

    def test_batch_predict_empty_list(self, client):
        """Test batch predict with empty list"""
        response = client.post("/batch_predict", json=[])
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_batch_predict_multiple_events(self, client, sample_event):
        """Test batch predict with multiple events"""
        events = [
            sample_event.model_dump(mode='json'),
            sample_event.model_dump(mode='json')
        ]

        response = client.post("/batch_predict", json=events)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "successful" in data
        assert "failed" in data
        assert "results" in data


class TestAPIValidation:
    """Test API input validation"""

    def test_invalid_json(self, client):
        """Test handling of invalid JSON"""
        response = client.post(
            "/predict",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_schema_validation(self, client):
        """Test Pydantic schema validation"""
        # Invalid IP address
        response = client.post(
            "/predict",
            json={"event": {
                "event_id": "test",
                "source_system": "test",
                "source_ip": "invalid.ip",
                "destination_ip": "8.8.8.8",
                "source_port": 12345,
                "destination_port": 80,
                "protocol": "tcp"
            }}
        )
        assert response.status_code == 422

    def test_port_range_validation(self, client):
        """Test port number validation"""
        # Port out of range
        response = client.post(
            "/predict",
            json={"event": {
                "event_id": "test",
                "source_system": "test",
                "source_ip": "192.168.1.1",
                "destination_ip": "8.8.8.8",
                "source_port": 99999,  # Invalid port
                "destination_port": 80,
                "protocol": "tcp"
            }}
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
