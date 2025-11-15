#!/usr/bin/env python3
"""
Example: Predict threat from a network event
"""

import requests
import json
from datetime import datetime


def main():
    """Demonstrate threat prediction API"""

    # API endpoint
    api_url = "http://localhost:8000/predict"

    # Sample network events
    events = [
        {
            "name": "Normal DNS Query",
            "event": {
                "event_id": "evt-001",
                "source_system": "zeek",
                "source_ip": "192.168.1.100",
                "destination_ip": "8.8.8.8",
                "source_port": 54321,
                "destination_port": 53,
                "protocol": "dns",
                "bytes_sent": 512,
                "bytes_received": 1024,
                "dns_query": "google.com"
            }
        },
        {
            "name": "Suspicious Port Scan",
            "event": {
                "event_id": "evt-002",
                "source_system": "zeek",
                "source_ip": "192.168.1.100",
                "destination_ip": "10.0.0.50",
                "source_port": 49152,
                "destination_port": 22,
                "protocol": "tcp",
                "bytes_sent": 100,
                "bytes_received": 0,
                "flags": "SYN"
            }
        },
        {
            "name": "High Entropy DNS Query",
            "event": {
                "event_id": "evt-003",
                "source_system": "zeek",
                "source_ip": "192.168.1.100",
                "destination_ip": "8.8.8.8",
                "source_port": 54322,
                "destination_port": 53,
                "protocol": "dns",
                "bytes_sent": 800,
                "bytes_received": 200,
                "dns_query": "a1b2c3d4e5f6g7h8i9j0k.malicious-domain.com"
            }
        }
    ]

    print("=" * 70)
    print("AI Threat Detection - Example Predictions")
    print("=" * 70)
    print()

    for example in events:
        print(f"Testing: {example['name']}")
        print("-" * 70)

        try:
            response = requests.post(
                api_url,
                json={"event": example['event']},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()

                print(f"Alert ID:          {result['alert_id']}")
                print(f"Threat Score:      {result['threat_score']:.4f}")
                print(f"Anomaly Score:     {result['anomaly_score']:.4f}")
                print(f"Severity:          {result['severity'].upper()}")
                print(f"Is Threat:         {'YES' if result['is_threat'] else 'NO'}")
                print(f"Model Confidence:  {result['model_confidence']:.4f}")
                print(f"Inference Time:    {result['inference_time_ms']:.2f} ms")
                print(f"\nTop Contributing Features:")

                for feature in result['top_features'][:3]:
                    print(f"  • {feature['feature']}: {feature['value']} "
                          f"(contribution: {feature['contribution']:.2f})")

                print(f"\nRecommended Action:")
                print(f"  {result['recommended_action']}")

            elif response.status_code == 503:
                print("⚠️  Models not loaded. Please train models first:")
                print("   jupyter notebook notebooks/01_model_training_demo.ipynb")

            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   {response.json()}")

        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Is the API server running?")
            print("   Start it with: make serve")
            return

        except Exception as e:
            print(f"❌ Error: {str(e)}")

        print()

    print("=" * 70)
    print("Example complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
