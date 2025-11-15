"""
Feature Extractor
Main class for extracting features from security events
"""

import math
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import numpy as np
import redis
import structlog

from ..data_pipeline.schemas import NetworkEvent, EndpointEvent, ApplicationLog


logger = structlog.get_logger(__name__)


class FeatureVector(BaseModel):
    """Complete feature vector for ML model input"""

    # Metadata
    source_ip: str
    timestamp: datetime
    event_id: str

    # Temporal aggregations (1-minute window)
    conn_count_1min: int = Field(default=0, description="Connection count in 1 minute")
    unique_dst_ips_1min: int = Field(default=0, description="Unique destination IPs in 1 minute")
    unique_dst_ports_1min: int = Field(default=0, description="Unique destination ports in 1 minute")
    unique_protocols_1min: int = Field(default=0, description="Unique protocols in 1 minute")

    # Temporal aggregations (5-minute window)
    conn_count_5min: int = Field(default=0, description="Connection count in 5 minutes")
    unique_dst_ips_5min: int = Field(default=0, description="Unique destination IPs in 5 minutes")
    unique_dst_ports_5min: int = Field(default=0, description="Unique destination ports in 5 minutes")

    # Temporal aggregations (1-hour window)
    conn_count_1hour: int = Field(default=0, description="Connection count in 1 hour")
    unique_dst_ips_1hour: int = Field(default=0, description="Unique destination IPs in 1 hour")
    unique_dst_ports_1hour: int = Field(default=0, description="Unique destination ports in 1 hour")

    # Statistical features
    payload_size_mean: float = Field(default=0.0, description="Mean payload size")
    payload_size_stddev: float = Field(default=0.0, description="Stddev of payload size")
    payload_entropy: float = Field(default=0.0, description="Shannon entropy of payload")
    dns_entropy: float = Field(default=0.0, description="DNS query entropy")
    http_ua_entropy: float = Field(default=0.0, description="HTTP User-Agent entropy")

    # Behavioral features
    is_novel_port: bool = Field(default=False, description="Never-before-seen port combination")
    is_new_country: bool = Field(default=False, description="Connection from new country")
    off_hours_activity: bool = Field(default=False, description="Activity outside business hours")
    peer_deviation_score: float = Field(default=0.0, description="Deviation from peer group")

    # Threat intelligence features
    ip_reputation_score: int = Field(default=0, description="IP reputation (-100 to 100)")
    mitre_technique_count: int = Field(default=0, description="Number of MITRE techniques matched")
    ioc_matches: int = Field(default=0, description="Threat intelligence IOC matches")

    # Protocol-specific features
    is_http: bool = Field(default=False)
    is_dns: bool = Field(default=False)
    is_ssh: bool = Field(default=False)

    def to_numpy_array(self) -> np.ndarray:
        """
        Convert feature vector to numpy array for ML model input

        Returns:
            np.ndarray: Feature values
        """
        # Select only numeric and boolean features (exclude metadata)
        features = [
            # Temporal (1min)
            self.conn_count_1min,
            self.unique_dst_ips_1min,
            self.unique_dst_ports_1min,
            self.unique_protocols_1min,

            # Temporal (5min)
            self.conn_count_5min,
            self.unique_dst_ips_5min,
            self.unique_dst_ports_5min,

            # Temporal (1hour)
            self.conn_count_1hour,
            self.unique_dst_ips_1hour,
            self.unique_dst_ports_1hour,

            # Statistical
            self.payload_size_mean,
            self.payload_size_stddev,
            self.payload_entropy,
            self.dns_entropy,
            self.http_ua_entropy,

            # Behavioral (convert bool to int)
            int(self.is_novel_port),
            int(self.is_new_country),
            int(self.off_hours_activity),
            self.peer_deviation_score,

            # Threat Intelligence
            self.ip_reputation_score,
            self.mitre_technique_count,
            self.ioc_matches,

            # Protocol-specific (convert bool to int)
            int(self.is_http),
            int(self.is_dns),
            int(self.is_ssh),
        ]

        return np.array(features, dtype=np.float32)

    @property
    def feature_count(self) -> int:
        """Get the number of features"""
        return len(self.to_numpy_array())


class FeatureExtractor:
    """
    Main feature extractor class

    Extracts features from security events using temporal aggregations,
    statistical calculations, and threat intelligence lookups
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        redis_url: str = "redis://localhost:6379/0"
    ):
        """
        Initialize feature extractor

        Args:
            redis_client: Optional Redis client (creates new if None)
            redis_url: Redis connection URL
        """
        if redis_client is None:
            self.redis = redis.from_url(redis_url, decode_responses=True)
        else:
            self.redis = redis_client

        logger.info("feature_extractor_initialized", redis_url=redis_url)

    def extract_from_network_event(
        self,
        event: NetworkEvent,
        lookback_windows: Dict[str, timedelta] = None
    ) -> FeatureVector:
        """
        Extract features from network event

        Args:
            event: NetworkEvent object
            lookback_windows: Time windows for aggregations

        Returns:
            FeatureVector object
        """
        if lookback_windows is None:
            lookback_windows = {
                "1min": timedelta(minutes=1),
                "5min": timedelta(minutes=5),
                "1hour": timedelta(hours=1)
            }

        # Initialize feature vector
        features = FeatureVector(
            source_ip=event.source_ip,
            timestamp=event.timestamp,
            event_id=event.event_id
        )

        # Extract temporal aggregation features
        features = self._extract_temporal_features(event, features, lookback_windows)

        # Extract statistical features
        features = self._extract_statistical_features(event, features)

        # Extract behavioral features
        features = self._extract_behavioral_features(event, features)

        # Extract threat intelligence features
        features = self._extract_threat_intelligence_features(event, features)

        # Protocol-specific features
        features.is_http = event.protocol.value in ["http", "https"]
        features.is_dns = event.protocol.value == "dns"
        features.is_ssh = event.protocol.value == "ssh"

        # Store current event data in Redis for future temporal aggregations
        self._store_event_data(event)

        return features

    def _extract_temporal_features(
        self,
        event: NetworkEvent,
        features: FeatureVector,
        lookback_windows: Dict[str, timedelta]
    ) -> FeatureVector:
        """
        Extract temporal aggregation features

        Args:
            event: NetworkEvent
            features: Partial FeatureVector
            lookback_windows: Time windows for aggregations

        Returns:
            Updated FeatureVector
        """
        source_ip = event.source_ip
        current_time = event.timestamp

        # Get historical data from Redis
        # 1-minute window
        features.conn_count_1min = self._get_connection_count(
            source_ip, current_time - lookback_windows["1min"], current_time
        )
        features.unique_dst_ips_1min = self._get_unique_count(
            source_ip, "dst_ips", current_time - lookback_windows["1min"], current_time
        )
        features.unique_dst_ports_1min = self._get_unique_count(
            source_ip, "dst_ports", current_time - lookback_windows["1min"], current_time
        )
        features.unique_protocols_1min = self._get_unique_count(
            source_ip, "protocols", current_time - lookback_windows["1min"], current_time
        )

        # 5-minute window
        features.conn_count_5min = self._get_connection_count(
            source_ip, current_time - lookback_windows["5min"], current_time
        )
        features.unique_dst_ips_5min = self._get_unique_count(
            source_ip, "dst_ips", current_time - lookback_windows["5min"], current_time
        )
        features.unique_dst_ports_5min = self._get_unique_count(
            source_ip, "dst_ports", current_time - lookback_windows["5min"], current_time
        )

        # 1-hour window
        features.conn_count_1hour = self._get_connection_count(
            source_ip, current_time - lookback_windows["1hour"], current_time
        )
        features.unique_dst_ips_1hour = self._get_unique_count(
            source_ip, "dst_ips", current_time - lookback_windows["1hour"], current_time
        )
        features.unique_dst_ports_1hour = self._get_unique_count(
            source_ip, "dst_ports", current_time - lookback_windows["1hour"], current_time
        )

        return features

    def _extract_statistical_features(
        self,
        event: NetworkEvent,
        features: FeatureVector
    ) -> FeatureVector:
        """
        Extract statistical features

        Args:
            event: NetworkEvent
            features: Partial FeatureVector

        Returns:
            Updated FeatureVector
        """
        # Payload statistics
        if event.payload:
            features.payload_entropy = self._calculate_entropy(event.payload)
        else:
            features.payload_entropy = 0.0

        # DNS entropy
        if event.dns_query:
            features.dns_entropy = self._calculate_entropy(event.dns_query)

        # HTTP User-Agent entropy
        if event.http_user_agent:
            features.http_ua_entropy = self._calculate_entropy(event.http_user_agent)

        # Payload size statistics (would need historical data)
        features.payload_size_mean = float(event.bytes_sent)
        features.payload_size_stddev = 0.0  # Simplified for now

        return features

    def _extract_behavioral_features(
        self,
        event: NetworkEvent,
        features: FeatureVector
    ) -> FeatureVector:
        """
        Extract behavioral features

        Args:
            event: NetworkEvent
            features: Partial FeatureVector

        Returns:
            Updated FeatureVector
        """
        # Check if port is novel (never seen before from this source)
        port_key = f"seen_ports:{event.source_ip}"
        is_new_port = not self.redis.sismember(port_key, str(event.destination_port))
        features.is_novel_port = is_new_port

        # Check if activity is outside business hours (8 AM - 5 PM)
        hour = event.timestamp.hour
        features.off_hours_activity = not (8 <= hour <= 17)

        # Simplified peer deviation (would need more sophisticated calculation)
        features.peer_deviation_score = 0.0

        # Country check (simplified - would need GeoIP lookup)
        features.is_new_country = False

        return features

    def _extract_threat_intelligence_features(
        self,
        event: NetworkEvent,
        features: FeatureVector
    ) -> FeatureVector:
        """
        Extract threat intelligence features

        Args:
            event: NetworkEvent
            features: Partial FeatureVector

        Returns:
            Updated FeatureVector
        """
        # IP reputation lookup from Redis cache
        reputation_key = f"reputation:{event.destination_ip}"
        reputation = self.redis.get(reputation_key)

        if reputation:
            features.ip_reputation_score = int(reputation)
        else:
            features.ip_reputation_score = 0  # Neutral

        # IOC matches
        ioc_key = f"iocs:{event.destination_ip}"
        features.ioc_matches = 1 if self.redis.exists(ioc_key) else 0

        # MITRE technique count (simplified)
        features.mitre_technique_count = 0

        return features

    def _calculate_entropy(self, data: str) -> float:
        """
        Calculate Shannon entropy of a string

        Args:
            data: Input string

        Returns:
            float: Entropy value (0-8 typically for ASCII)
        """
        if not data:
            return 0.0

        # Count character frequencies
        frequencies = {}
        for char in data:
            frequencies[char] = frequencies.get(char, 0) + 1

        # Calculate entropy
        entropy = 0.0
        data_len = len(data)

        for count in frequencies.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def _get_connection_count(
        self,
        source_ip: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """
        Get connection count for source IP in time window

        Args:
            source_ip: Source IP address
            start_time: Window start time
            end_time: Window end time

        Returns:
            int: Connection count
        """
        # Use Redis sorted set for time-series data
        key = f"connections:{source_ip}"
        count = self.redis.zcount(
            key,
            start_time.timestamp(),
            end_time.timestamp()
        )
        return count

    def _get_unique_count(
        self,
        source_ip: str,
        field: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """
        Get unique count of field values in time window

        Args:
            source_ip: Source IP address
            field: Field name (dst_ips, dst_ports, protocols)
            start_time: Window start time
            end_time: Window end time

        Returns:
            int: Unique count
        """
        # Simplified implementation using Redis sets
        # In production, would use time-windowed HyperLogLog
        key = f"{field}:{source_ip}"
        count = self.redis.scard(key)
        return count

    def _store_event_data(self, event: NetworkEvent) -> None:
        """
        Store event data in Redis for future aggregations

        Args:
            event: NetworkEvent
        """
        source_ip = event.source_ip
        timestamp = event.timestamp.timestamp()

        # Store connection in sorted set (by timestamp)
        conn_key = f"connections:{source_ip}"
        self.redis.zadd(conn_key, {event.event_id: timestamp})
        self.redis.expire(conn_key, 3600)  # 1 hour TTL

        # Store unique destination IPs
        dst_ip_key = f"dst_ips:{source_ip}"
        self.redis.sadd(dst_ip_key, event.destination_ip)
        self.redis.expire(dst_ip_key, 3600)

        # Store unique destination ports
        dst_port_key = f"dst_ports:{source_ip}"
        self.redis.sadd(dst_port_key, str(event.destination_port))
        self.redis.expire(dst_port_key, 3600)

        # Store protocols
        protocol_key = f"protocols:{source_ip}"
        self.redis.sadd(protocol_key, event.protocol.value)
        self.redis.expire(protocol_key, 3600)

        # Store seen ports
        port_key = f"seen_ports:{source_ip}"
        self.redis.sadd(port_key, str(event.destination_port))
        self.redis.expire(port_key, 86400 * 30)  # 30 days TTL

    def close(self) -> None:
        """Close Redis connection"""
        self.redis.close()


# Example usage
if __name__ == "__main__":
    from ..data_pipeline.schemas import NetworkEvent, Protocol
    import uuid

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Create feature extractor
    extractor = FeatureExtractor()

    # Create sample network event
    event = NetworkEvent(
        event_id=f"net-{uuid.uuid4().hex[:12]}",
        source_system="zeek",
        source_ip="192.168.1.100",
        destination_ip="8.8.8.8",
        source_port=54321,
        destination_port=53,
        protocol=Protocol.DNS,
        bytes_sent=512,
        bytes_received=1024,
        dns_query="example.com"
    )

    # Extract features
    features = extractor.extract_from_network_event(event)

    print("Extracted features:")
    print(f"Source IP: {features.source_ip}")
    print(f"Connections (1min): {features.conn_count_1min}")
    print(f"Unique dst ports (1min): {features.unique_dst_ports_1min}")
    print(f"DNS entropy: {features.dns_entropy:.4f}")
    print(f"Novel port: {features.is_novel_port}")
    print(f"Off-hours activity: {features.off_hours_activity}")
    print(f"\nFeature vector shape: {features.to_numpy_array().shape}")
    print(f"Feature count: {features.feature_count}")

    extractor.close()
