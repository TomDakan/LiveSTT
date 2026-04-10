"""
Start a NATS container with host-exposed port, run per-service
integration tests, then tear down.

Usage:
    uv run python scripts/run_integration_tests.py [pytest args...]
    just test-integration          # wraps this script
"""

import subprocess
import sys
import time

CONTAINER_NAME = "livestt-integration-nats"
NATS_PORT = 4222
HEALTH_TIMEOUT_S = 15


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)  # type: ignore[arg-type]


def _nats_up() -> None:
    """Start an ephemeral NATS container with JetStream and host port."""
    # Remove stale container if present
    _run(["docker", "rm", "-f", CONTAINER_NAME])

    result = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{NATS_PORT}:4222",
            "nats:2.10-alpine",
            "-js",
        ]
    )
    if result.returncode != 0:
        print(f"Failed to start NATS container:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Wait for NATS to be ready
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        check = _run(["docker", "exec", CONTAINER_NAME, "nats-server", "--health"])
        if check.returncode == 0:
            print(f"NATS ready on localhost:{NATS_PORT}")
            return
        time.sleep(0.5)

    print("NATS failed to become healthy", file=sys.stderr)
    _nats_down()
    sys.exit(1)


def _nats_down() -> None:
    """Stop and remove the NATS container."""
    _run(["docker", "rm", "-f", CONTAINER_NAME])
    print("NATS container removed")


def _run_tests(extra_args: list[str]) -> int:
    """Run pytest with integration marker, return exit code."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "integration",
        "--no-cov",
        "-v",
        *extra_args,
    ]
    result = subprocess.run(cmd)
    return result.returncode


def main() -> None:
    extra_args = sys.argv[1:]

    _nats_up()
    try:
        rc = _run_tests(extra_args)
    finally:
        _nats_down()

    sys.exit(rc)


if __name__ == "__main__":
    main()
