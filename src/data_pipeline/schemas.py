"""
Data schemas for security events
Defines Pydantic models for validation and serialization
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, IPvAnyAddress
from enum import Enum


class EventType(str, Enum):
    """Event type enumeration"""
    NETWORK = "network"
    ENDPOINT = "endpoint"
    APPLICATION = "application"
    THREAT_INTEL = "threat_intel"


class Protocol(str, Enum):
    """Network protocol enumeration"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"
    SSH = "ssh"
    OTHER = "other"


class Severity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BaseEvent(BaseModel):
    """Base event model with common fields"""

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp in UTC"
    )
    event_id: str = Field(
        ...,
        description="Unique event identifier",
        min_length=1
    )
    event_type: EventType = Field(
        ...,
        description="Type of security event"
    )
    source_system: str = Field(
        ...,
        description="System that generated the event (e.g., 'zeek', 'sysmon')",
        min_length=1
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional event metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-15T21:45:00Z",
                "event_id": "evt-12345",
                "event_type": "network",
                "source_system": "zeek",
                "metadata": {"collector_version": "1.0"}
            }
        }


class NetworkEvent(BaseEvent):
    """Network event model (Zeek, Suricata, NetFlow)"""

    source_ip: str = Field(
        ...,
        description="Source IP address"
    )
    destination_ip: str = Field(
        ...,
        description="Destination IP address"
    )
    source_port: int = Field(
        ...,
        ge=0,
        le=65535,
        description="Source port number"
    )
    destination_port: int = Field(
        ...,
        ge=0,
        le=65535,
        description="Destination port number"
    )
    protocol: Protocol = Field(
        ...,
        description="Network protocol"
    )
    bytes_sent: int = Field(
        default=0,
        ge=0,
        description="Bytes sent from source to destination"
    )
    bytes_received: int = Field(
        default=0,
        ge=0,
        description="Bytes received from destination"
    )
    packets_sent: int = Field(
        default=0,
        ge=0,
        description="Number of packets sent"
    )
    packets_received: int = Field(
        default=0,
        ge=0,
        description="Number of packets received"
    )
    flags: Optional[str] = Field(
        default=None,
        description="TCP flags or protocol-specific flags"
    )
    payload: Optional[str] = Field(
        default=None,
        description="Network payload (truncated)",
        max_length=10000
    )
    dns_query: Optional[str] = Field(
        default=None,
        description="DNS query domain (if DNS protocol)"
    )
    http_method: Optional[str] = Field(
        default=None,
        description="HTTP request method (if HTTP/HTTPS)"
    )
    http_uri: Optional[str] = Field(
        default=None,
        description="HTTP request URI"
    )
    http_user_agent: Optional[str] = Field(
        default=None,
        description="HTTP User-Agent header"
    )
    http_status_code: Optional[int] = Field(
        default=None,
        ge=100,
        le=599,
        description="HTTP response status code"
    )

    event_type: EventType = Field(default=EventType.NETWORK)

    @field_validator('source_ip', 'destination_ip')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """Validate IP address format"""
        try:
            # Basic IP validation (more comprehensive validation can be added)
            parts = v.split('.')
            if len(parts) != 4:
                raise ValueError("Invalid IPv4 address")
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    raise ValueError("Invalid IPv4 address")
            return v
        except Exception as e:
            raise ValueError(f"Invalid IP address: {v}") from e

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-15T21:45:00Z",
                "event_id": "net-12345",
                "event_type": "network",
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


class EndpointEvent(BaseEvent):
    """Endpoint event model (Sysmon, osquery, EDR)"""

    hostname: str = Field(
        ...,
        description="Endpoint hostname",
        min_length=1
    )
    username: Optional[str] = Field(
        default=None,
        description="Username associated with the event"
    )
    process_name: Optional[str] = Field(
        default=None,
        description="Process name"
    )
    process_id: Optional[int] = Field(
        default=None,
        ge=0,
        description="Process ID (PID)"
    )
    parent_process_name: Optional[str] = Field(
        default=None,
        description="Parent process name"
    )
    parent_process_id: Optional[int] = Field(
        default=None,
        ge=0,
        description="Parent process ID (PPID)"
    )
    command_line: Optional[str] = Field(
        default=None,
        description="Full command line",
        max_length=5000
    )
    file_path: Optional[str] = Field(
        default=None,
        description="File path involved in the event"
    )
    file_hash_md5: Optional[str] = Field(
        default=None,
        description="MD5 hash of file",
        pattern=r"^[a-fA-F0-9]{32}$"
    )
    file_hash_sha256: Optional[str] = Field(
        default=None,
        description="SHA256 hash of file",
        pattern=r"^[a-fA-F0-9]{64}$"
    )
    registry_key: Optional[str] = Field(
        default=None,
        description="Registry key (Windows)"
    )
    registry_value: Optional[str] = Field(
        default=None,
        description="Registry value (Windows)"
    )
    network_connections: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Network connections made by process"
    )
    event_code: Optional[int] = Field(
        default=None,
        description="Windows Event ID or similar"
    )

    event_type: EventType = Field(default=EventType.ENDPOINT)

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-15T21:45:00Z",
                "event_id": "ep-12345",
                "event_type": "endpoint",
                "source_system": "sysmon",
                "hostname": "workstation-01",
                "username": "john.doe",
                "process_name": "powershell.exe",
                "process_id": 1234,
                "command_line": "powershell.exe -ExecutionPolicy Bypass",
                "event_code": 1
            }
        }


class ApplicationLog(BaseEvent):
    """Application log event model"""

    application_name: str = Field(
        ...,
        description="Application name",
        min_length=1
    )
    log_level: str = Field(
        ...,
        description="Log level (DEBUG, INFO, WARN, ERROR, CRITICAL)"
    )
    message: str = Field(
        ...,
        description="Log message",
        max_length=10000
    )
    source_ip: Optional[str] = Field(
        default=None,
        description="Source IP if applicable"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID associated with the log"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier"
    )
    http_method: Optional[str] = Field(
        default=None,
        description="HTTP method if web application"
    )
    http_status_code: Optional[int] = Field(
        default=None,
        ge=100,
        le=599,
        description="HTTP status code"
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="Response time in milliseconds"
    )
    error_trace: Optional[str] = Field(
        default=None,
        description="Error stack trace if applicable"
    )

    event_type: EventType = Field(default=EventType.APPLICATION)

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-15T21:45:00Z",
                "event_id": "app-12345",
                "event_type": "application",
                "source_system": "nginx",
                "application_name": "web-server",
                "log_level": "INFO",
                "message": "GET /api/users successful",
                "source_ip": "192.168.1.100",
                "http_method": "GET",
                "http_status_code": 200,
                "response_time_ms": 45.2
            }
        }


class ThreatIntelligence(BaseModel):
    """Threat intelligence feed data"""

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="IOC timestamp"
    )
    ioc_type: str = Field(
        ...,
        description="Type of indicator (ip, domain, hash, url)"
    )
    ioc_value: str = Field(
        ...,
        description="Indicator value"
    )
    threat_type: str = Field(
        ...,
        description="Threat classification (malware, c2, phishing, etc.)"
    )
    severity: Severity = Field(
        ...,
        description="Threat severity"
    )
    source: str = Field(
        ...,
        description="Intelligence source (misp, virustotal, etc.)"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Threat description"
    )
    mitre_techniques: Optional[List[str]] = Field(
        default=None,
        description="MITRE ATT&CK technique IDs"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Additional tags"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-15T21:45:00Z",
                "ioc_type": "ip",
                "ioc_value": "1.2.3.4",
                "threat_type": "c2",
                "severity": "high",
                "source": "misp",
                "confidence_score": 0.95,
                "mitre_techniques": ["T1071.001"],
                "tags": ["apt29", "cobalt-strike"]
            }
        }


class Alert(BaseModel):
    """Generated alert model"""

    alert_id: str = Field(
        ...,
        description="Unique alert identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Alert generation time"
    )
    severity: Severity = Field(
        ...,
        description="Alert severity"
    )
    threat_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="ML model threat score (0-1)"
    )
    threat_type: str = Field(
        ...,
        description="Detected threat type"
    )
    source_ip: Optional[str] = Field(
        default=None,
        description="Source IP address"
    )
    destination_ip: Optional[str] = Field(
        default=None,
        description="Destination IP address"
    )
    hostname: Optional[str] = Field(
        default=None,
        description="Affected hostname"
    )
    model_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score"
    )
    top_features: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top contributing features (SHAP values)"
    )
    recommended_action: str = Field(
        ...,
        description="Recommended response action"
    )
    mitre_techniques: Optional[List[str]] = Field(
        default=None,
        description="MITRE ATT&CK techniques"
    )
    related_events: Optional[List[str]] = Field(
        default=None,
        description="Related event IDs"
    )
    is_duplicate: bool = Field(
        default=False,
        description="Flag indicating if this is a duplicate alert"
    )
    original_alert_id: Optional[str] = Field(
        default=None,
        description="Original alert ID if this is a duplicate"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "alert-12847",
                "timestamp": "2025-11-15T21:45:00Z",
                "severity": "high",
                "threat_score": 0.92,
                "threat_type": "port_scanning",
                "source_ip": "192.168.1.100",
                "model_confidence": 0.89,
                "top_features": [
                    {
                        "feature": "unique_dst_ports_week",
                        "value": 47,
                        "contribution": 0.31
                    }
                ],
                "recommended_action": "Isolate host, investigate recent activity",
                "mitre_techniques": ["T1046"]
            }
        }
