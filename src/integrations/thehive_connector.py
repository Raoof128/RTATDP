"""
TheHive SOAR Platform Integration
Automatically creates cases for critical alerts
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

from ..data_pipeline.schemas import Alert, Severity


logger = structlog.get_logger(__name__)


class TheHiveConnector:
    """
    Integration with TheHive Security Incident Response Platform

    Creates cases, tasks, and observables for threat investigation
    """

    def __init__(
        self,
        thehive_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize TheHive connector

        Args:
            thehive_url: TheHive instance URL
            api_key: API key for authentication
        """
        self.thehive_url = thehive_url or os.getenv('THEHIVE_URL', 'http://thehive:9000')
        self.api_key = api_key or os.getenv('THEHIVE_API_KEY')

        if not self.api_key:
            logger.warning("thehive_api_key_not_configured")

        try:
            from thehive4py.api import TheHiveApi
            from thehive4py.models import Case, CaseTask, CaseObservable

            self.api = TheHiveApi(self.thehive_url, self.api_key, cert=False)
            self.Case = Case
            self.CaseTask = CaseTask
            self.CaseObservable = CaseObservable

            logger.info("thehive_connector_initialized", url=self.thehive_url)

        except ImportError:
            logger.error("thehive4py_not_installed")
            self.api = None

    def create_case_from_alert(self, alert: Alert) -> Optional[str]:
        """
        Create a case in TheHive from an alert

        Args:
            alert: Alert object

        Returns:
            str: Case ID if successful, None otherwise
        """
        if not self.api:
            logger.error("thehive_api_not_available")
            return None

        try:
            # Map severity to TLP
            severity_map = {
                Severity.CRITICAL: 3,  # RED
                Severity.HIGH: 2,      # AMBER
                Severity.MEDIUM: 1,    # GREEN
                Severity.LOW: 0        # WHITE
            }

            # Build case description
            description = f"""
# AI-Detected Threat

**Threat Score**: {alert.threat_score:.4f}
**Source IP**: {alert.source_ip or 'N/A'}
**Destination IP**: {alert.destination_ip or 'N/A'}
**Hostname**: {alert.hostname or 'N/A'}

## Top Contributing Features

{self._format_features(alert.top_features)}

## Recommended Actions

{alert.recommended_action}

## MITRE ATT&CK Techniques

{', '.join(alert.mitre_techniques) if alert.mitre_techniques else 'None identified'}

## Related Events

{', '.join(alert.related_events) if alert.related_events else 'None'}

---
*This case was automatically created by the AI Threat Detection System*
            """.strip()

            # Create case
            case = self.Case(
                title=f"AI Detected: {alert.threat_type} - {alert.source_ip or alert.hostname}",
                description=description,
                severity=severity_map.get(alert.severity, 2),
                tlp=severity_map.get(alert.severity, 2),
                tags=[
                    'ai_detection',
                    alert.threat_type,
                    f'severity_{alert.severity.value}'
                ] + (alert.mitre_techniques or [])
            )

            response = self.api.create_case(case)

            if response.status_code == 201:
                case_data = response.json()
                case_id = case_data['id']

                logger.info(
                    "thehive_case_created",
                    alert_id=alert.alert_id,
                    case_id=case_id
                )

                # Create default tasks
                self._create_default_tasks(case_id)

                # Add observables
                self._add_observables(case_id, alert)

                return case_id
            else:
                logger.error(
                    "thehive_case_creation_failed",
                    alert_id=alert.alert_id,
                    status_code=response.status_code
                )
                return None

        except Exception as e:
            logger.error(
                "error_creating_thehive_case",
                alert_id=alert.alert_id,
                error=str(e)
            )
            return None

    def _format_features(self, features: list) -> str:
        """Format top features for case description"""
        if not features:
            return "No feature information available"

        lines = []
        for feature in features[:5]:  # Top 5
            lines.append(
                f"- **{feature.get('feature', 'Unknown')}**: "
                f"{feature.get('value', 'N/A')} "
                f"(contribution: {feature.get('contribution', 0):.2f})"
            )

        return '\n'.join(lines)

    def _create_default_tasks(self, case_id: str) -> None:
        """Create default investigation tasks"""
        if not self.api:
            return

        tasks = [
            "Verify alert - check for false positive",
            "Investigate source IP/host activity",
            "Check for lateral movement",
            "Review recent authentication logs",
            "Analyze network traffic patterns",
            "Determine if containment is required",
            "Document findings and remediation steps"
        ]

        for task_title in tasks:
            try:
                task = self.CaseTask(
                    title=task_title,
                    status='Waiting'
                )
                self.api.create_case_task(case_id, task)
            except Exception as e:
                logger.warning(
                    "failed_to_create_task",
                    case_id=case_id,
                    task=task_title,
                    error=str(e)
                )

    def _add_observables(self, case_id: str, alert: Alert) -> None:
        """Add observables (IOCs) to the case"""
        if not self.api:
            return

        observables = []

        # Add IPs
        if alert.source_ip:
            observables.append(('ip', alert.source_ip, 'Source IP'))
        if alert.destination_ip:
            observables.append(('ip', alert.destination_ip, 'Destination IP'))

        # Add hostname
        if alert.hostname:
            observables.append(('hostname', alert.hostname, 'Affected Host'))

        # Create observables
        for data_type, value, description in observables:
            try:
                observable = self.CaseObservable(
                    dataType=data_type,
                    data=value,
                    message=description,
                    tlp=2,
                    ioc=True
                )
                self.api.create_case_observable(case_id, observable)
            except Exception as e:
                logger.warning(
                    "failed_to_create_observable",
                    case_id=case_id,
                    observable=value,
                    error=str(e)
                )


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
        severity=Severity.CRITICAL,
        threat_score=0.96,
        threat_type="lateral_movement",
        source_ip="192.168.1.100",
        destination_ip="192.168.1.50",
        hostname="workstation-42",
        model_confidence=0.94,
        top_features=[
            {"feature": "unique_dst_ips_1hour", "value": 127, "contribution": 0.41},
            {"feature": "off_hours_activity", "value": 1, "contribution": 0.28}
        ],
        recommended_action="Immediately isolate both hosts, investigate for compromise indicators",
        mitre_techniques=["T1021", "T1078"]
    )

    # Initialize connector
    connector = TheHiveConnector()

    # Create case
    print("Creating TheHive case from alert...")
    case_id = connector.create_case_from_alert(sample_alert)

    if case_id:
        print(f"✓ Case created successfully: {case_id}")
    else:
        print("✗ Failed to create case")
