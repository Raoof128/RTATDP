"""
Splunk HTTP Event Collector (HEC) Integration
Exports alerts to Splunk SIEM
"""

import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from ..data_pipeline.schemas import Alert


logger = structlog.get_logger(__name__)


class SplunkExporter:
    """
    Export alerts to Splunk using HTTP Event Collector (HEC)

    Splunk HEC provides a fast, efficient way to send data to Splunk
    """

    def __init__(
        self,
        hec_url: Optional[str] = None,
        hec_token: Optional[str] = None,
        index: str = "security",
        sourcetype: str = "_json",
        verify_ssl: bool = True
    ):
        """
        Initialize Splunk exporter

        Args:
            hec_url: Splunk HEC endpoint URL
            hec_token: HEC authentication token
            index: Splunk index to send events to
            sourcetype: Splunk sourcetype
            verify_ssl: Whether to verify SSL certificates
        """
        self.hec_url = hec_url or os.getenv('SPLUNK_HEC_URL', 'https://splunk-hec.internal:8088/services/collector')
        self.hec_token = hec_token or os.getenv('SPLUNK_HEC_TOKEN')
        self.index = index
        self.sourcetype = sourcetype
        self.verify_ssl = verify_ssl

        if not self.hec_token:
            logger.warning("splunk_hec_token_not_configured")

        self.headers = {
            'Authorization': f'Splunk {self.hec_token}',
            'Content-Type': 'application/json'
        }

        logger.info(
            "splunk_exporter_initialized",
            hec_url=self.hec_url,
            index=index
        )

    def export_alert(self, alert: Alert) -> bool:
        """
        Export a single alert to Splunk

        Args:
            alert: Alert object to export

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert alert to Splunk event format
            payload = {
                'event': alert.model_dump(mode='json'),
                'source': 'ai_threat_detector',
                'sourcetype': self.sourcetype,
                'index': self.index,
                'time': alert.timestamp.timestamp() if hasattr(alert, 'timestamp') else None
            }

            # Send to Splunk HEC
            response = requests.post(
                self.hec_url,
                json=payload,
                headers=self.headers,
                verify=self.verify_ssl,
                timeout=10
            )

            response.raise_for_status()

            logger.info(
                "alert_exported_to_splunk",
                alert_id=alert.alert_id,
                status_code=response.status_code
            )

            return True

        except requests.exceptions.RequestException as e:
            logger.error(
                "splunk_export_failed",
                alert_id=alert.alert_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
        except Exception as e:
            logger.error(
                "unexpected_error_exporting_to_splunk",
                alert_id=alert.alert_id,
                error=str(e)
            )
            return False

    def export_batch(self, alerts: List[Alert]) -> Dict[str, int]:
        """
        Export multiple alerts to Splunk

        Args:
            alerts: List of alerts to export

        Returns:
            dict: Statistics (total, successful, failed)
        """
        stats = {
            "total": len(alerts),
            "successful": 0,
            "failed": 0
        }

        for alert in alerts:
            if self.export_alert(alert):
                stats["successful"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            "batch_export_to_splunk_completed",
            total=stats["total"],
            successful=stats["successful"],
            failed=stats["failed"]
        )

        return stats

    def test_connection(self) -> bool:
        """
        Test connection to Splunk HEC

        Returns:
            bool: True if connection successful
        """
        try:
            test_payload = {
                'event': {'test': 'connection'},
                'sourcetype': '_json',
                'source': 'ai_threat_detector_test'
            }

            response = requests.post(
                self.hec_url,
                json=test_payload,
                headers=self.headers,
                verify=self.verify_ssl,
                timeout=5
            )

            response.raise_for_status()

            logger.info("splunk_connection_test_successful")
            return True

        except Exception as e:
            logger.error("splunk_connection_test_failed", error=str(e))
            return False


# Example usage
if __name__ == "__main__":
    from ..data_pipeline.schemas import Severity
    import uuid

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Create sample alert
    sample_alert = Alert(
        alert_id=f"alert-{uuid.uuid4().hex[:12]}",
        timestamp=datetime.utcnow(),
        severity=Severity.HIGH,
        threat_score=0.92,
        threat_type="port_scanning",
        source_ip="192.168.1.100",
        model_confidence=0.89,
        top_features=[
            {"feature": "unique_dst_ports_week", "value": 47, "contribution": 0.31}
        ],
        recommended_action="Isolate host, investigate recent activity",
        mitre_techniques=["T1046"]
    )

    # Initialize exporter
    exporter = SplunkExporter()

    # Test connection
    print("Testing Splunk connection...")
    if exporter.test_connection():
        print("✓ Connection successful")

        # Export alert
        print("\nExporting sample alert...")
        if exporter.export_alert(sample_alert):
            print(f"✓ Alert {sample_alert.alert_id} exported successfully")
    else:
        print("✗ Connection failed - check HEC URL and token")
