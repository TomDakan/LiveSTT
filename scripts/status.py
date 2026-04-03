#!/usr/bin/env python3
"""One-shot status summary: container health, NATS streams, disk usage."""

from __future__ import annotations

import json
import subprocess  # nosec B404


def _run(cmd: list[str], *, timeout: int = 10) -> str:
    """Run a command and return stdout, or empty string on failure."""
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


def _header(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


def container_health() -> None:
    _header("Container Health")
    raw = _run(
        [
            "docker",
            "compose",
            "ps",
            "-a",
            "--format",
            "json",
        ]
    )
    if not raw:
        print("  (no containers found - is the stack running?)")
        return

    for line in raw.splitlines():
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = c.get("Name", c.get("Service", "?"))
        state = c.get("State", "?")
        health = c.get("Health", "")
        status = c.get("Status", "")
        health_str = f" ({health})" if health else ""
        print(f"  {name:<25} {state}{health_str:<20} {status}")


def nats_streams() -> None:
    _header("NATS Streams")
    # Use the monitoring endpoint via wget inside the container
    raw = _run(
        [
            "docker",
            "exec",
            "nats",
            "wget",
            "-qO-",
            "http://localhost:8222/jsz?streams=true",
        ]
    )
    if not raw:
        print("  (NATS monitoring not available - enable with -m 8222)")
        print("  Use 'just nats-streams' for detailed stream info.")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("  (could not parse NATS response)")
        return

    for account in data.get("account_details", []):
        for stream in account.get("stream_detail", []):
            config = stream.get("config", stream)
            state = stream.get("state", {})
            name = stream.get("name", config.get("name", "?"))
            msgs = state.get("messages", 0)
            size = state.get("bytes", 0)
            consumers = state.get("consumer_count", 0)
            size_mb = size / (1024 * 1024)
            print(
                f"  {name:<25} "
                f"msgs={msgs:<10} "
                f"size={size_mb:.1f}MB  "
                f"consumers={consumers}"
            )


def disk_usage() -> None:
    _header("Docker Volumes")
    raw = _run(
        [
            "docker",
            "system",
            "df",
            "-v",
            "--format",
            "json",
        ]
    )
    if not raw:
        # Fallback: just show volume names and sizes
        raw = _run(["docker", "volume", "ls", "--format", "json"])
        if not raw:
            print("  (could not query Docker volumes)")
            return
        for line in raw.splitlines():
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = v.get("Name", "?")
            if name.startswith("livestt_"):
                print(f"  {name}")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("  (could not parse Docker response)")
        return

    volumes = data.get("Volumes", [])
    if not volumes:
        print("  (no volumes)")
        return

    for v in volumes:
        name = v.get("Name", "?")
        if not name.startswith("livestt_"):
            continue
        size = v.get("Size", "?")
        print(f"  {name:<40} {size}")


def main() -> None:
    print("Live STT - System Status")
    container_health()
    nats_streams()
    disk_usage()
    print()


if __name__ == "__main__":
    main()
