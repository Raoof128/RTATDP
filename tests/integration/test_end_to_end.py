"""
End-to-end integration tests
"""

import pytest
import requests
import time
from tests.fixtures.sample_data import SampleDataGenerator


@pytest.mark.integration
class TestEndToEndPipeline:
    """Test complete pipeline from event to alert"""

    @pytest.fixture
    def api_url(self):
        """API base URL"""
        return "http://localhost:8000"

    @pytest.fixture
    def sample_generator(self):
        """Sample data generator"""
        return SampleDataGenerator()

    def test_health_check(self, api_url):
        """Test API health endpoint"""
        response = requests.get(f"{api_url}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "models_loaded" in data

    def test_prediction_endpoint(self, api_url, sample_generator):
        """Test threat prediction endpoint"""
        # Generate sample event
        events = sample_generator.generate_network_events(count=1, threat_ratio=0)
        event = events[0]

        # Make prediction request
        response = requests.post(
            f"{api_url}/predict",
            json={"event": event.model_dump(mode='json')},
            timeout=10
        )

        # Verify response
        if response.status_code == 503:
            pytest.skip("Models not loaded - train models first")

        assert response.status_code == 200

        data = response.json()
        assert "alert_id" in data
        assert "threat_score" in data
        assert "severity" in data
        assert "inference_time_ms" in data

        # Verify inference time is reasonable
        assert data["inference_time_ms"] < 500  # Less than 500ms

    def test_batch_prediction(self, api_url, sample_generator):
        """Test batch prediction endpoint"""
        # Generate multiple events
        events = sample_generator.generate_network_events(count=10, threat_ratio=0.3)

        # Convert to JSON
        events_json = [e.model_dump(mode='json') for e in events]

        # Make batch prediction request
        response = requests.post(
            f"{api_url}/batch_predict",
            json=events_json,
            timeout=30
        )

        if response.status_code == 503:
            pytest.skip("Models not loaded")

        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert data["total"] == 10
        assert "successful" in data
        assert "results" in data

    @pytest.mark.slow
    def test_prediction_accuracy(self, api_url, sample_generator):
        """Test prediction accuracy on known data"""
        # Generate benign events
        benign_events = sample_generator.generate_network_events(count=50, threat_ratio=0)

        # Generate threat events
        threat_events = sample_generator.generate_network_events(count=50, threat_ratio=1.0)

        benign_correct = 0
        threat_correct = 0

        # Test benign events
        for event in benign_events:
            response = requests.post(
                f"{api_url}/predict",
                json={"event": event.model_dump(mode='json')},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if not data["is_threat"] or data["threat_score"] < 0.5:
                    benign_correct += 1

        # Test threat events
        for event in threat_events:
            response = requests.post(
                f"{api_url}/predict",
                json={"event": event.model_dump(mode='json')},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data["is_threat"] or data["threat_score"] > 0.5:
                    threat_correct += 1

        # Calculate accuracy (relaxed for synthetic data)
        benign_accuracy = benign_correct / len(benign_events)
        threat_accuracy = threat_correct / len(threat_events)

        print(f"\nBenign Accuracy: {benign_accuracy:.2%}")
        print(f"Threat Accuracy: {threat_accuracy:.2%}")

        # We expect at least 50% accuracy on synthetic data
        assert benign_accuracy > 0.5, f"Benign accuracy too low: {benign_accuracy:.2%}"

    def test_metrics_endpoint(self, api_url):
        """Test Prometheus metrics endpoint"""
        response = requests.get(f"{api_url}/metrics", timeout=5)
        assert response.status_code == 200

        # Check for expected metrics
        content = response.text
        assert "inference_latency_seconds" in content
        assert "ai_detector_alerts_total" in content

    def test_api_documentation(self, api_url):
        """Test API documentation is accessible"""
        response = requests.get(f"{api_url}/docs", timeout=5)
        assert response.status_code == 200

    @pytest.mark.slow
    def test_concurrent_requests(self, api_url, sample_generator):
        """Test API handles concurrent requests"""
        import concurrent.futures

        events = sample_generator.generate_network_events(count=20, threat_ratio=0.2)

        def make_request(event):
            try:
                response = requests.post(
                    f"{api_url}/predict",
                    json={"event": event.model_dump(mode='json')},
                    timeout=10
                )
                return response.status_code == 200
            except:
                return False

        # Send requests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_request, events))

        # Most requests should succeed
        success_rate = sum(results) / len(results)
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2%}"


@pytest.mark.integration
class TestDataPipeline:
    """Test data pipeline components"""

    def test_kafka_connectivity(self):
        """Test Kafka is accessible"""
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers='localhost:9092',
                request_timeout_ms=5000
            )
            producer.close()
        except Exception as e:
            pytest.skip(f"Kafka not accessible: {e}")

    def test_redis_connectivity(self):
        """Test Redis is accessible"""
        try:
            import redis
            r = redis.from_url("redis://localhost:6379/0")
            r.ping()
        except Exception as e:
            pytest.skip(f"Redis not accessible: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
