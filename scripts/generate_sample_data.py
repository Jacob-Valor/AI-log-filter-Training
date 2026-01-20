#!/usr/bin/env python3
"""
Generate sample training data for development and testing.

This creates synthetic log data with proper labels for training.
Use this to bootstrap the model before you have real labeled data.
"""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Sample log templates by category
TEMPLATES = {
    "critical": [
        "ALERT: Malware detected - {malware_type} found in {path}",
        "CRITICAL: Brute force attack detected from {ip} - {count} failed attempts",
        "SECURITY: Privilege escalation attempt by user {user} on {host}",
        "THREAT: Ransomware activity detected - files being encrypted in {path}",
        "ALERT: SQL injection attempt detected in request from {ip}",
        "CRITICAL: C2 beacon detected - host {host} communicating with {ip}",
        "SECURITY: Unauthorized root access attempt from {ip}",
        "ALERT: Data exfiltration detected - {size}MB transferred to {ip}",
        "CRITICAL: Mimikatz execution detected on {host}",
        "THREAT: Cobalt Strike beacon identified on {host}",
    ],
    "suspicious": [
        "WARNING: Failed login attempt for user {user} from {ip}",
        "NOTICE: Access denied for {user} accessing {path}",
        "WARNING: Unusual network activity from {host} to port {port}",
        "ALERT: Port scan detected from {ip} on ports {port_range}",
        "WARNING: Permission denied for {user} on {resource}",
        "NOTICE: Failed authentication from unusual location {location}",
        "WARNING: Suspicious PowerShell execution on {host}",
        "ALERT: Multiple failed SSH attempts from {ip}",
        "NOTICE: Unauthorized access attempt to {resource}",
        "WARNING: Unusual outbound traffic to {ip}:{port}",
    ],
    "routine": [
        "INFO: User {user} logged in successfully from {ip}",
        "NOTICE: Configuration updated for {service}",
        "INFO: Service {service} started successfully on {host}",
        "DEBUG: Session created for user {user}",
        "INFO: Backup completed successfully - {size}MB archived",
        "NOTICE: Password changed for user {user}",
        "INFO: New connection established from {ip}",
        "DEBUG: Request processed in {latency}ms",
        "INFO: User {user} logged out",
        "NOTICE: System update applied successfully",
    ],
    "noise": [
        "DEBUG: Health check endpoint called - status OK",
        "TRACE: Heartbeat received from {host}",
        "DEBUG: Prometheus scrape completed",
        "TRACE: Keep-alive ping from {ip}",
        "DEBUG: Metrics exported to {endpoint}",
        "TRACE: Timer triggered for scheduled task",
        "DEBUG: Cache hit for key {key}",
        "TRACE: Connection pool status: {count} active",
        "DEBUG: GC completed in {latency}ms",
        "TRACE: Telemetry data sent",
    ],
}

# Sample values for template substitution
SAMPLE_VALUES = {
    "malware_type": ["Trojan.Generic", "Ransomware.WannaCry", "Backdoor.Cobalt", "Worm.Conficker"],
    "path": ["/usr/bin/suspicious", "/tmp/payload.exe", "/home/user/downloads/invoice.pdf", "C:\\Windows\\Temp\\malware.dll"],
    "ip": ["192.168.1.100", "10.0.0.50", "172.16.0.25", "203.0.113.42", "198.51.100.17"],
    "count": ["5", "10", "15", "50", "100"],
    "user": ["admin", "root", "jsmith", "svc_account", "backup_user"],
    "host": ["web-server-01", "db-master", "app-node-03", "jumpbox", "workstation-42"],
    "size": ["50", "100", "500", "1024", "2048"],
    "port": ["22", "443", "3389", "8080", "3306"],
    "port_range": ["1-1000", "20-25", "80,443,8080", "3306,5432"],
    "resource": ["/etc/passwd", "/var/log/auth.log", "database.users", "admin_panel"],
    "location": ["Russia", "China", "Unknown VPN", "Tor Exit Node"],
    "service": ["nginx", "mysql", "redis", "kafka", "elasticsearch"],
    "latency": ["5", "15", "50", "100", "250"],
    "endpoint": ["prometheus:9090", "grafana:3000", "localhost:8080"],
    "key": ["user:123", "session:abc", "cache:data"],
}


def generate_log(category: str) -> str:
    """Generate a single log message."""
    template = random.choice(TEMPLATES[category])

    # Substitute placeholders
    for key, values in SAMPLE_VALUES.items():
        placeholder = "{" + key + "}"
        if placeholder in template:
            template = template.replace(placeholder, random.choice(values))

    return template


def generate_dataset(
    output_path: str,
    total_samples: int = 10000,
    distribution: dict = None
):
    """Generate a labeled dataset."""
    if distribution is None:
        # Realistic distribution
        distribution = {
            "critical": 0.02,    # 2%
            "suspicious": 0.12,  # 12%
            "routine": 0.46,     # 46%
            "noise": 0.40,       # 40%
        }

    samples = []

    for category, ratio in distribution.items():
        count = int(total_samples * ratio)
        for _ in range(count):
            message = generate_log(category)
            timestamp = datetime.now() - timedelta(
                hours=random.randint(0, 720),  # Last 30 days
                minutes=random.randint(0, 59)
            )
            samples.append({
                "timestamp": timestamp.isoformat(),
                "message": message,
                "category": category,
                "source": f"log-source-{random.randint(1, 10)}"
            })

    # Shuffle
    random.shuffle(samples)

    # Write to CSV
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "message", "category", "source"])
        writer.writeheader()
        writer.writerows(samples)

    print(f"Generated {len(samples)} samples to {output_path}")
    print("Distribution:")
    for category in ["critical", "suspicious", "routine", "noise"]:
        count = sum(1 for s in samples if s["category"] == category)
        print(f"  {category}: {count} ({count/len(samples)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Generate sample training data")
    parser.add_argument(
        "--output",
        type=str,
        default="data/labeled/train.csv",
        help="Output CSV file path"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=10000,
        help="Number of samples to generate"
    )
    parser.add_argument(
        "--test-split",
        action="store_true",
        help="Also generate test.csv file"
    )

    args = parser.parse_args()

    # Generate training data
    generate_dataset(args.output, args.samples)

    # Generate test data
    if args.test_split:
        test_path = args.output.replace("train.csv", "test.csv")
        generate_dataset(test_path, args.samples // 5)


if __name__ == "__main__":
    main()
