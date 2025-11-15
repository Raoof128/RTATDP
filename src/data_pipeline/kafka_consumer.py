"""
Kafka Event Consumer
Consumes security events from Kafka topics and processes them
"""

import json
import signal
import sys
from typing import Callable, Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import structlog

from .schemas import NetworkEvent, EndpointEvent, ApplicationLog, ThreatIntelligence


logger = structlog.get_logger(__name__)


class KafkaEventConsumer:
    """
    Kafka consumer for processing security events

    Supports automatic deserialization and event routing
    """

    def __init__(
        self,
        topics: list[str],
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "threat-detection-consumer",
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        **kwargs
    ):
        """
        Initialize Kafka consumer

        Args:
            topics: List of Kafka topics to subscribe to
            bootstrap_servers: Kafka broker addresses
            group_id: Consumer group ID
            auto_offset_reset: Where to start consuming (earliest/latest)
            enable_auto_commit: Whether to auto-commit offsets
            **kwargs: Additional KafkaConsumer configuration
        """
        self.topics = topics
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.running = False

        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset,
                enable_auto_commit=enable_auto_commit,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                **kwargs
            )

            logger.info(
                "kafka_consumer_initialized",
                topics=topics,
                group_id=group_id,
                bootstrap_servers=bootstrap_servers
            )

            # Setup graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

        except Exception as e:
            logger.error("kafka_consumer_init_failed", error=str(e))
            raise

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("shutdown_signal_received", signal=signum)
        self.stop()

    def parse_event(self, message_value: Dict[str, Any]) -> Optional[Any]:
        """
        Parse raw message into appropriate event object

        Args:
            message_value: Deserialized message value

        Returns:
            Parsed event object or None if parsing fails
        """
        try:
            event_type = message_value.get("event_type")

            if event_type == "network":
                return NetworkEvent(**message_value)
            elif event_type == "endpoint":
                return EndpointEvent(**message_value)
            elif event_type == "application":
                return ApplicationLog(**message_value)
            elif event_type == "threat_intel":
                return ThreatIntelligence(**message_value)
            else:
                logger.warning("unknown_event_type", event_type=event_type)
                return None

        except Exception as e:
            logger.error(
                "event_parsing_failed",
                error=str(e),
                message_value=message_value
            )
            return None

    def consume(
        self,
        callback: Callable[[Any], None],
        max_messages: Optional[int] = None,
        timeout_ms: int = 1000
    ) -> int:
        """
        Consume messages and process with callback

        Args:
            callback: Function to call for each event
            max_messages: Maximum number of messages to consume (None = infinite)
            timeout_ms: Consumer poll timeout

        Returns:
            int: Number of messages processed
        """
        self.running = True
        messages_processed = 0

        try:
            logger.info("starting_message_consumption")

            while self.running:
                # Poll for messages
                message_batch = self.consumer.poll(
                    timeout_ms=timeout_ms,
                    max_records=500
                )

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            # Parse event
                            event = self.parse_event(message.value)

                            if event is None:
                                continue

                            # Process with callback
                            callback(event)

                            messages_processed += 1

                            # Log progress periodically
                            if messages_processed % 1000 == 0:
                                logger.info(
                                    "consumption_progress",
                                    messages_processed=messages_processed
                                )

                            # Check max messages limit
                            if max_messages and messages_processed >= max_messages:
                                logger.info(
                                    "max_messages_reached",
                                    messages_processed=messages_processed
                                )
                                self.running = False
                                break

                        except Exception as e:
                            logger.error(
                                "message_processing_error",
                                error=str(e),
                                topic=topic_partition.topic,
                                partition=topic_partition.partition,
                                offset=message.offset
                            )
                            continue

                    if not self.running:
                        break

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
        except Exception as e:
            logger.error("consumption_error", error=str(e))
        finally:
            logger.info(
                "consumption_stopped",
                total_messages_processed=messages_processed
            )

        return messages_processed

    def stop(self) -> None:
        """Stop consuming messages"""
        logger.info("stopping_consumer")
        self.running = False

    def close(self) -> None:
        """Close the Kafka consumer"""
        try:
            self.consumer.close()
            logger.info("kafka_consumer_closed")
        except Exception as e:
            logger.error("kafka_close_failed", error=str(e))

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class EventProcessor:
    """
    Example event processor that routes events to different handlers
    """

    def __init__(self):
        """Initialize event processor"""
        self.event_counts = {
            "network": 0,
            "endpoint": 0,
            "application": 0,
            "threat_intel": 0
        }

    def process_event(self, event: Any) -> None:
        """
        Process a single event

        Args:
            event: Parsed event object
        """
        event_type = event.event_type.value if hasattr(event, 'event_type') else "unknown"

        # Route to appropriate handler
        if isinstance(event, NetworkEvent):
            self.handle_network_event(event)
        elif isinstance(event, EndpointEvent):
            self.handle_endpoint_event(event)
        elif isinstance(event, ApplicationLog):
            self.handle_application_log(event)
        else:
            logger.warning("unhandled_event_type", event_type=event_type)

        # Update counters
        if event_type in self.event_counts:
            self.event_counts[event_type] += 1

    def handle_network_event(self, event: NetworkEvent) -> None:
        """
        Handle network event

        Args:
            event: NetworkEvent object
        """
        # Example: Log high-volume connections
        if event.bytes_sent > 1000000:  # > 1MB
            logger.info(
                "high_volume_connection",
                source_ip=event.source_ip,
                destination_ip=event.destination_ip,
                bytes_sent=event.bytes_sent
            )

    def handle_endpoint_event(self, event: EndpointEvent) -> None:
        """
        Handle endpoint event

        Args:
            event: EndpointEvent object
        """
        # Example: Flag suspicious PowerShell execution
        if event.process_name and "powershell" in event.process_name.lower():
            if event.command_line and any(
                flag in event.command_line.lower()
                for flag in ["-executionpolicy bypass", "-windowstyle hidden"]
            ):
                logger.warning(
                    "suspicious_powershell_execution",
                    hostname=event.hostname,
                    command_line=event.command_line
                )

    def handle_application_log(self, event: ApplicationLog) -> None:
        """
        Handle application log

        Args:
            event: ApplicationLog object
        """
        # Example: Log authentication failures
        if "authentication" in event.message.lower() and "failed" in event.message.lower():
            logger.warning(
                "authentication_failure",
                application=event.application_name,
                source_ip=event.source_ip,
                message=event.message
            )

    def get_statistics(self) -> Dict[str, int]:
        """
        Get processing statistics

        Returns:
            dict: Event counts by type
        """
        return self.event_counts.copy()


# Example usage
if __name__ == "__main__":
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Topics to consume
    topics = [
        "security.events.network",
        "security.events.endpoint",
        "security.events.application"
    ]

    # Initialize consumer and processor
    consumer = KafkaEventConsumer(
        topics=topics,
        bootstrap_servers="localhost:9092",
        group_id="threat-detection-consumer"
    )

    processor = EventProcessor()

    try:
        # Start consuming
        print(f"Starting consumption from topics: {topics}")
        print("Press Ctrl+C to stop...")

        messages_processed = consumer.consume(
            callback=processor.process_event,
            max_messages=None  # Consume indefinitely
        )

        # Print statistics
        print(f"\nTotal messages processed: {messages_processed}")
        print("Statistics:", processor.get_statistics())

    finally:
        consumer.close()
