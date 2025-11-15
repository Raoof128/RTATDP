"""
Kafka Event Producer
Publishes security events to Kafka topics
"""

import json
import logging
from typing import Union, Dict, Any
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError
import structlog

from .schemas import NetworkEvent, EndpointEvent, ApplicationLog, ThreatIntelligence, BaseEvent


logger = structlog.get_logger(__name__)


class KafkaEventProducer:
    """
    Kafka producer for publishing security events

    Supports multiple event types and automatic topic routing
    """

    # Topic mapping by event type
    TOPIC_MAP = {
        "network": "security.events.network",
        "endpoint": "security.events.endpoint",
        "application": "security.events.application",
        "threat_intel": "security.threat_intelligence"
    }

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        compression_type: str = "snappy",
        acks: int = 1,
        retries: int = 3,
        max_in_flight_requests: int = 5,
        **kwargs
    ):
        """
        Initialize Kafka producer

        Args:
            bootstrap_servers: Kafka broker addresses
            compression_type: Compression algorithm (snappy, gzip, lz4)
            acks: Number of acknowledgments required
            retries: Number of retries on failure
            max_in_flight_requests: Max unacknowledged requests
            **kwargs: Additional KafkaProducer configuration
        """
        self.bootstrap_servers = bootstrap_servers
        self.compression_type = compression_type

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                compression_type=compression_type,
                acks=acks,
                retries=retries,
                max_in_flight_requests_per_connection=max_in_flight_requests,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                **kwargs
            )
            logger.info(
                "kafka_producer_initialized",
                bootstrap_servers=bootstrap_servers,
                compression=compression_type
            )
        except Exception as e:
            logger.error("kafka_producer_init_failed", error=str(e))
            raise

    def send_event(
        self,
        event: Union[NetworkEvent, EndpointEvent, ApplicationLog, ThreatIntelligence, BaseEvent],
        key: str = None,
        partition: int = None
    ) -> bool:
        """
        Send a single event to appropriate Kafka topic

        Args:
            event: Event object (must be a Pydantic model)
            key: Optional message key for partitioning
            partition: Optional specific partition

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Determine topic based on event type
            event_type = event.event_type.value
            topic = self.TOPIC_MAP.get(event_type)

            if not topic:
                logger.error(
                    "unknown_event_type",
                    event_type=event_type,
                    event_id=event.event_id
                )
                return False

            # Convert event to dictionary
            event_dict = event.model_dump(mode='json')

            # Use source_ip as key for partitioning (ensures events from same IP go to same partition)
            if key is None:
                if hasattr(event, 'source_ip') and event.source_ip:
                    key = event.source_ip
                elif hasattr(event, 'hostname') and event.hostname:
                    key = event.hostname
                else:
                    key = event.event_id

            # Send to Kafka
            future = self.producer.send(
                topic,
                value=event_dict,
                key=key,
                partition=partition
            )

            # Wait for send to complete (with timeout)
            record_metadata = future.get(timeout=10)

            logger.info(
                "event_sent_to_kafka",
                event_id=event.event_id,
                event_type=event_type,
                topic=record_metadata.topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset
            )

            return True

        except KafkaError as e:
            logger.error(
                "kafka_send_failed",
                event_id=event.event_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
        except Exception as e:
            logger.error(
                "unexpected_error_sending_event",
                event_id=event.event_id,
                error=str(e)
            )
            return False

    def send_batch(
        self,
        events: list[Union[NetworkEvent, EndpointEvent, ApplicationLog, ThreatIntelligence]]
    ) -> Dict[str, int]:
        """
        Send multiple events in batch

        Args:
            events: List of event objects

        Returns:
            dict: Statistics (total, successful, failed)
        """
        stats = {
            "total": len(events),
            "successful": 0,
            "failed": 0
        }

        for event in events:
            if self.send_event(event):
                stats["successful"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            "batch_send_completed",
            total=stats["total"],
            successful=stats["successful"],
            failed=stats["failed"]
        )

        return stats

    def flush(self, timeout: float = None) -> None:
        """
        Flush any pending messages

        Args:
            timeout: Maximum time to wait for flush
        """
        try:
            self.producer.flush(timeout=timeout)
            logger.info("kafka_producer_flushed")
        except Exception as e:
            logger.error("kafka_flush_failed", error=str(e))

    def close(self) -> None:
        """Close the Kafka producer"""
        try:
            self.producer.close()
            logger.info("kafka_producer_closed")
        except Exception as e:
            logger.error("kafka_close_failed", error=str(e))

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class SimulatedEventGenerator:
    """
    Generate simulated security events for testing

    Useful for load testing and development when real data sources aren't available
    """

    def __init__(self, seed: int = 42):
        """
        Initialize event generator

        Args:
            seed: Random seed for reproducibility
        """
        import random
        from faker import Faker

        random.seed(seed)
        self.faker = Faker()
        Faker.seed(seed)

    def generate_network_event(self, is_malicious: bool = False) -> NetworkEvent:
        """
        Generate a simulated network event

        Args:
            is_malicious: Whether to generate suspicious characteristics

        Returns:
            NetworkEvent object
        """
        import random
        import uuid

        protocols = ["tcp", "udp", "http", "https", "dns"]

        if is_malicious:
            # Generate suspicious patterns
            dst_ports = [22, 23, 445, 3389, 4444, 8080, 9999]  # Suspicious ports
            bytes_sent = random.randint(10000, 1000000)
        else:
            # Normal traffic
            dst_ports = [80, 443, 53, 25, 587]
            bytes_sent = random.randint(100, 5000)

        return NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self.faker.ipv4_private(),
            destination_ip=self.faker.ipv4_public(),
            source_port=random.randint(49152, 65535),
            destination_port=random.choice(dst_ports),
            protocol=random.choice(protocols),
            bytes_sent=bytes_sent,
            bytes_received=random.randint(100, 10000),
            packets_sent=random.randint(1, 100),
            packets_received=random.randint(1, 100)
        )

    def generate_endpoint_event(self, is_malicious: bool = False) -> EndpointEvent:
        """
        Generate a simulated endpoint event

        Args:
            is_malicious: Whether to generate suspicious characteristics

        Returns:
            EndpointEvent object
        """
        import random
        import uuid

        if is_malicious:
            # Suspicious PowerShell execution
            process_names = ["powershell.exe", "cmd.exe", "wscript.exe"]
            command_lines = [
                "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden",
                "cmd.exe /c whoami && net user",
                "wscript.exe malicious.vbs"
            ]
        else:
            # Normal processes
            process_names = ["chrome.exe", "outlook.exe", "teams.exe"]
            command_lines = [
                "chrome.exe --no-sandbox",
                "outlook.exe /safe",
                "teams.exe --enable-logging"
            ]

        return EndpointEvent(
            event_id=f"ep-{uuid.uuid4().hex[:12]}",
            source_system="sysmon",
            hostname=self.faker.hostname(),
            username=self.faker.user_name(),
            process_name=random.choice(process_names),
            process_id=random.randint(1000, 9999),
            command_line=random.choice(command_lines),
            event_code=1
        )

    def generate_application_log(self, is_error: bool = False) -> ApplicationLog:
        """
        Generate a simulated application log

        Args:
            is_error: Whether to generate error log

        Returns:
            ApplicationLog object
        """
        import random
        import uuid

        if is_error:
            log_level = "ERROR"
            messages = [
                "Database connection failed",
                "Authentication error: Invalid credentials",
                "SQL injection attempt detected"
            ]
            status_codes = [400, 401, 403, 500, 503]
        else:
            log_level = "INFO"
            messages = [
                "User logged in successfully",
                "GET /api/users completed",
                "POST /api/data processed"
            ]
            status_codes = [200, 201, 204]

        return ApplicationLog(
            event_id=f"app-{uuid.uuid4().hex[:12]}",
            source_system="nginx",
            application_name="web-server",
            log_level=log_level,
            message=random.choice(messages),
            source_ip=self.faker.ipv4(),
            http_method=random.choice(["GET", "POST", "PUT", "DELETE"]),
            http_status_code=random.choice(status_codes),
            response_time_ms=random.uniform(10, 500)
        )


# Example usage
if __name__ == "__main__":
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Initialize producer
    producer = KafkaEventProducer(bootstrap_servers="localhost:9092")

    # Generate and send simulated events
    generator = SimulatedEventGenerator()

    # Send 10 network events
    print("Sending network events...")
    for i in range(10):
        event = generator.generate_network_event(is_malicious=(i % 3 == 0))
        producer.send_event(event)

    # Send 10 endpoint events
    print("Sending endpoint events...")
    for i in range(10):
        event = generator.generate_endpoint_event(is_malicious=(i % 4 == 0))
        producer.send_event(event)

    # Flush and close
    producer.flush()
    producer.close()

    print("Events sent successfully!")
