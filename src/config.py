"""
Configuration Management
Centralized configuration for the threat detection system
"""

import os
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    """Kafka configuration"""
    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka broker addresses"
    )
    network_events_topic: str = Field(
        default="security.events.network",
        description="Topic for network events"
    )
    endpoint_events_topic: str = Field(
        default="security.events.endpoint",
        description="Topic for endpoint events"
    )
    application_logs_topic: str = Field(
        default="security.events.application",
        description="Topic for application logs"
    )
    threat_intel_topic: str = Field(
        default="security.threat_intelligence",
        description="Topic for threat intelligence"
    )
    consumer_group_id: str = Field(
        default="threat-detection-consumer",
        description="Consumer group ID"
    )
    compression_type: str = Field(
        default="snappy",
        description="Compression algorithm"
    )

    class Config:
        env_prefix = "KAFKA_"


class RedisSettings(BaseSettings):
    """Redis configuration"""
    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    max_connections: int = Field(
        default=50,
        description="Maximum connection pool size"
    )
    socket_timeout: int = Field(
        default=5,
        description="Socket timeout in seconds"
    )
    default_ttl: int = Field(
        default=3600,
        description="Default TTL for keys in seconds"
    )

    class Config:
        env_prefix = "REDIS_"


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration"""
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="threat_detection", description="Database name")
    username: str = Field(default="detector", description="Database username")
    password: str = Field(default="detector_password", description="Database password")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")

    class Config:
        env_prefix = "DB_"

    @property
    def connection_url(self) -> str:
        """Get database connection URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class ModelSettings(BaseSettings):
    """ML model configuration"""
    ensemble_models_path: str = Field(
        default="models/ensemble",
        description="Path to ensemble models"
    )
    anomaly_models_path: str = Field(
        default="models/anomaly",
        description="Path to anomaly detection models"
    )
    model_version: str = Field(
        default="1.0.0",
        description="Current model version"
    )
    ensemble_weights: dict = Field(
        default={"random_forest": 0.4, "xgboost": 0.35, "lightgbm": 0.25},
        description="Ensemble model weights"
    )
    anomaly_contamination: float = Field(
        default=0.02,
        description="Expected anomaly rate"
    )
    threat_threshold: float = Field(
        default=0.85,
        description="Threat score threshold"
    )
    anomaly_threshold: float = Field(
        default=1.0,
        description="Anomaly score threshold"
    )

    class Config:
        env_prefix = "MODEL_"


class APISettings(BaseSettings):
    """API server configuration"""
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, description="API port")
    workers: int = Field(default=4, description="Number of worker processes")
    reload: bool = Field(default=False, description="Enable auto-reload")
    log_level: str = Field(default="info", description="Log level")
    cors_origins: List[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )
    max_request_size: int = Field(
        default=10485760,  # 10MB
        description="Maximum request size in bytes"
    )
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )

    class Config:
        env_prefix = "API_"


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration"""
    prometheus_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    structured_logging: bool = Field(
        default=True,
        description="Enable structured logging"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    trace_sampling_rate: float = Field(
        default=0.1,
        description="Distributed tracing sampling rate"
    )

    class Config:
        env_prefix = "MONITORING_"


class SIEMSettings(BaseSettings):
    """SIEM/SOAR integration configuration"""
    splunk_hec_url: Optional[str] = Field(
        default=None,
        description="Splunk HEC endpoint URL"
    )
    splunk_hec_token: Optional[str] = Field(
        default=None,
        description="Splunk HEC token"
    )
    splunk_index: str = Field(
        default="security",
        description="Splunk index"
    )
    thehive_url: Optional[str] = Field(
        default=None,
        description="TheHive instance URL"
    )
    thehive_api_key: Optional[str] = Field(
        default=None,
        description="TheHive API key"
    )
    auto_create_cases: bool = Field(
        default=True,
        description="Auto-create cases for critical alerts"
    )
    case_severity_threshold: str = Field(
        default="high",
        description="Minimum severity for case creation"
    )

    class Config:
        env_prefix = "SIEM_"


class PerformanceSettings(BaseSettings):
    """Performance and scalability settings"""
    max_events_per_second: int = Field(
        default=500000,
        description="Maximum events per second"
    )
    batch_size: int = Field(
        default=128,
        description="Batch size for inference"
    )
    max_latency_ms: int = Field(
        default=100,
        description="Maximum allowed latency in milliseconds"
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable feature caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds"
    )

    class Config:
        env_prefix = "PERF_"


class Settings(BaseSettings):
    """Main application settings"""

    # Environment
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )

    # Component settings
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    api: APISettings = Field(default_factory=APISettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    siem: SIEMSettings = Field(default_factory=SIEMSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings (singleton)

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment

    Returns:
        New Settings instance
    """
    global _settings
    _settings = Settings()
    return _settings


# Example usage
if __name__ == "__main__":
    settings = get_settings()

    print("=== Threat Detection System Configuration ===")
    print(f"Environment: {settings.environment}")
    print(f"Debug Mode: {settings.debug}")
    print(f"\nKafka: {settings.kafka.bootstrap_servers}")
    print(f"Redis: {settings.redis.url}")
    print(f"Database: {settings.database.connection_url}")
    print(f"API: {settings.api.host}:{settings.api.port}")
    print(f"Model Threshold: {settings.models.threat_threshold}")
    print(f"Max Events/Sec: {settings.performance.max_events_per_second}")
