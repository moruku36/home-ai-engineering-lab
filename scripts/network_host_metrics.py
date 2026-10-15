#!/usr/bin/env python3
"""Read explicitly selected host NIC counters into node_exporter's textfile directory.

Run on the Ubuntu HOST, never inside the exporter container. No probes or packets.
No scheduler is installed by this script. Python standard library only.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time


def render(raw, interfaces, now):
    if not interfaces or len(set(interfaces)) != len(interfaces):
        raise ValueError("select one or more unique host interfaces")
    counters = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        name, values = line.rsplit(":", 1)
        fields = values.split()
        if len(fields) != 16:
            raise ValueError("invalid /proc/net/dev row")
        numbers = [int(value) for value in fields]
        if any(value < 0 for value in numbers):
            raise ValueError("negative interface counter")
        counters[name.strip()] = numbers
    missing = set(interfaces) - counters.keys()
    if missing:
        raise ValueError("selected interface not found")
    lines = ["# HELP lab_host_network_snapshot_timestamp_seconds Last successful host snapshot.",
             "# TYPE lab_host_network_snapshot_timestamp_seconds gauge",
             f"lab_host_network_snapshot_timestamp_seconds {float(now)}"]
    metrics = {"receive_bytes": 0, "receive_errors": 2, "receive_dropped": 3,
               "transmit_bytes": 8, "transmit_errors": 10, "transmit_dropped": 11}
    for metric, index in metrics.items():
        full = f"lab_host_network_{metric}_total"
        lines.extend([f"# HELP {full} Selected Ubuntu host interface counter.",
                      f"# TYPE {full} counter"])
        for interface in interfaces:
            # Prometheus string escaping agrees with JSON for ordinary Linux NIC names.
            if not interface or any(ord(c) < 32 or ord(c) > 126 for c in interface):
                raise ValueError("invalid interface name")
            lines.append(f"{full}{{device={json.dumps(interface)}}} {counters[interface][index]}")
    return "\n".join(lines) + "\n"


def atomic_write(destination, content):
    destination = Path(destination)
    # Directory must be deliberately prepared by the operator; do not create it here.
    fd, name = tempfile.mkstemp(prefix=".network-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o644)  # exporter runs as nobody; only metrics, no IP/MAC/DNS
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Source is intentionally fixed to the host's procfs in production.
    content = render(Path("/proc/net/dev").read_text(), args.interface, time.time())
    atomic_write(args.output, content)


if __name__ == "__main__":
    main()
