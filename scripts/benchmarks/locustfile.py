#!/usr/bin/env python3
"""
Locust load testing configuration for AI Threat Detection Pipeline

Usage:
    # Web UI mode
    locust -f locustfile.py --host=http://localhost:8000

    # Headless mode
    locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m --headless

    # With specific tags
    locust -f locustfile.py --host=http://localhost:8000 --tags predict --headless
"""

import sys
import random
from locust import HttpUser, task, between, tag

# Add project root to path
sys.path.insert(0, '/home/user/RTATDP')
from tests.fixtures.sample_data import SampleDataGenerator


class ThreatDetectionUser(HttpUser):
    """Simulated user for load testing"""

    # Wait between 0.5 and 2 seconds between tasks
    wait_time = between(0.5, 2)

    def on_start(self):
        """Initialize user session"""
        self.generator = SampleDataGenerator()
        # Generate a pool of events to use
        self.network_events = self.generator.generate_network_events(count=100, threat_ratio=0.3)
        self.endpoint_events = self.generator.generate_endpoint_events(count=50)

    @tag('health')
    @task(1)
    def check_health(self):
        """Health check endpoint"""
        self.client.get("/health")

    @tag('predict', 'core')
    @task(20)
    def predict_threat(self):
        """Single prediction request"""
        event = random.choice(self.network_events)
        self.client.post(
            "/predict",
            json={"event": event.model_dump(mode='json')},
            name="/predict"
        )

    @tag('batch', 'core')
    @task(5)
    def batch_predict(self):
        """Batch prediction request"""
        batch_size = random.choice([5, 10, 20])
        events = random.sample(self.network_events, batch_size)
        events_json = [e.model_dump(mode='json') for e in events]

        self.client.post(
            "/batch_predict",
            json=events_json,
            name=f"/batch_predict (size={batch_size})"
        )

    @tag('metrics')
    @task(1)
    def get_metrics(self):
        """Prometheus metrics endpoint"""
        self.client.get("/metrics")

    @tag('info')
    @task(2)
    def model_info(self):
        """Model information endpoint"""
        self.client.get("/model/info")


class HighLoadUser(HttpUser):
    """User for high-load stress testing"""

    # No wait time - constant load
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Initialize user session"""
        self.generator = SampleDataGenerator()
        self.network_events = self.generator.generate_network_events(count=200, threat_ratio=0.5)

    @tag('stress', 'predict')
    @task(50)
    def rapid_fire_predictions(self):
        """Rapid-fire prediction requests"""
        event = random.choice(self.network_events)
        self.client.post(
            "/predict",
            json={"event": event.model_dump(mode='json')},
            name="/predict [stress]"
        )

    @tag('stress', 'batch')
    @task(10)
    def large_batch_predictions(self):
        """Large batch predictions"""
        batch_size = 50
        events = random.sample(self.network_events, min(batch_size, len(self.network_events)))
        events_json = [e.model_dump(mode='json') for e in events]

        self.client.post(
            "/batch_predict",
            json=events_json,
            name="/batch_predict [stress]"
        )


class RealisticUser(HttpUser):
    """Realistic usage pattern"""

    wait_time = between(2, 10)

    def on_start(self):
        """Initialize user session"""
        self.generator = SampleDataGenerator()
        self.network_events = self.generator.generate_network_events(count=50, threat_ratio=0.1)

        # Check health first
        self.client.get("/health")

    @tag('realistic')
    @task(15)
    def normal_prediction(self):
        """Normal prediction flow"""
        event = random.choice(self.network_events)

        # Sometimes check health first
        if random.random() < 0.1:
            self.client.get("/health")

        # Make prediction
        response = self.client.post(
            "/predict",
            json={"event": event.model_dump(mode='json')},
            name="/predict [realistic]"
        )

        # Sometimes fetch metrics after prediction
        if random.random() < 0.05:
            self.client.get("/metrics")

    @tag('realistic')
    @task(3)
    def batch_analysis(self):
        """Batch analysis flow"""
        batch_size = random.choice([10, 15, 20])
        events = random.sample(self.network_events, min(batch_size, len(self.network_events)))
        events_json = [e.model_dump(mode='json') for e in events]

        self.client.post(
            "/batch_predict",
            json=events_json,
            name="/batch_predict [realistic]"
        )

    @tag('realistic')
    @task(2)
    def check_system_status(self):
        """Check system status"""
        self.client.get("/health")
        self.client.get("/model/info")
