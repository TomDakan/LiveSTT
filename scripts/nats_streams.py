#!/usr/bin/env python3
"""Pretty-print NATS JetStream stream configs and current state."""

from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
from typing import Any


def _run(cmd: list[str], *, timeout: int = 10) -> str:
    try:
        result = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _fmt_bytes(n: int) -> str:
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024**3):.1f} GB"
    if n >= 1024 * 1024:
        return f"{n / (1024**2):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def _fmt_duration(ns: int) -> str:
    """Format nanosecond duration to human-readable."""
    if ns == 0:
        return "unlimited"
    secs = ns // 1_000_000_000
    if secs >= 86400:
        return f"{secs // 86400}d"
    if secs >= 3600:
        return f"{secs // 3600}h"
    if secs >= 60:
        return f"{secs // 60}m"
    return f"{secs}s"


def _print_stream(stream: dict[str, Any]) -> None:
    """Print a single stream's config and state."""
    # /jsz puts config fields at the stream level, not nested under "config"
    config = stream.get("config", stream)
    state = stream.get("state", {})

    name = stream.get("name", config.get("name", "?"))
    print(f"{'=' * 60}")
    print(f"  Stream: {name}")
    print(f"{'=' * 60}")

    # Config — try both top-level and nested "config" keys
    subjects = config.get("subjects", [])
    if subjects:
        print(f"  Subjects:    {', '.join(subjects)}")
    storage = config.get("storage", "")
    if storage:
        print(f"  Storage:     {storage}")
    retention = config.get("retention", "")
    if retention:
        print(f"  Retention:   {retention}")
    max_age = config.get("max_age", 0)
    if max_age:
        print(f"  Max age:     {_fmt_duration(max_age)}")
    max_bytes = config.get("max_bytes", -1)
    if max_bytes > 0:
        print(f"  Max bytes:   {_fmt_bytes(max_bytes)}")
    max_msgs = config.get("max_msgs", -1)
    if max_msgs > 0:
        print(f"  Max msgs:    {max_msgs}")
    max_per_subj = config.get("max_msgs_per_subject", -1)
    if max_per_subj > 0:
        print(f"  Max/subject: {max_per_subj}")
    max_msg_size = config.get("max_msg_size", -1)
    if max_msg_size > 0:
        print(f"  Max msg sz:  {_fmt_bytes(max_msg_size)}")

    # State
    print("  ---")
    print(f"  Messages:    {state.get('messages', 0)}")
    print(f"  Bytes:       {_fmt_bytes(state.get('bytes', 0))}")
    print(f"  Seq range:   {state.get('first_seq', 0)} .. {state.get('last_seq', 0)}")
    print(f"  Consumers:   {state.get('consumer_count', 0)}")

    # Consumer details
    for cons in stream.get("consumer_detail", []):
        cname = cons.get("name", "?")
        delivered = cons.get("delivered", {})
        ack_floor = cons.get("ack_floor", {})
        num_pending = cons.get("num_pending", 0)
        print(
            f"    - {cname:<20} "
            f"delivered={delivered.get('stream_seq', 0)}  "
            f"acked={ack_floor.get('stream_seq', 0)}  "
            f"pending={num_pending}"
        )

    print()


def main() -> int:
    raw = _run(
        [
            "docker",
            "exec",
            "nats",
            "wget",
            "-qO-",
            "http://localhost:8222/jsz?streams=true&consumers=true&config=true",
        ]
    )
    if not raw:
        print(
            "Error: Could not reach NATS monitoring endpoint.\n"
            "Is the stack running? (NATS needs -m 8222)"
        )
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Error: Could not parse NATS response.")
        return 1

    streams_found = False
    for account in data.get("account_details", []):
        for stream in account.get("stream_detail", []):
            streams_found = True
            _print_stream(stream)

    if not streams_found:
        print("No streams found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
