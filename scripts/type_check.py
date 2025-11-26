"""
Cross-platform script to run MyPy type checking.
Usage:
    python scripts/type_check.py [service_name]

If service_name is provided, runs MyPy for that service.
If not, runs MyPy for all services and root modules.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Define root modules to check
ROOT_MODULES = ["src", "scripts", "bootstrap.py"]


def run_mypy(target: str) -> bool:
    """Run MyPy on the target path."""
    print(f"Type checking {target}...")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--no-incremental",
                "--no-warn-unused-configs",
                target,
            ],
            check=False,  # We handle the return code manually
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running MyPy on {target}: {e}")
        return False


def has_python_files(path: Path) -> bool:
    """Check if directory contains .py files."""
    return any(path.rglob("*.py"))


def check_services(services_dir: Path) -> bool:
    """Check all services in the services directory."""
    failed = False
    if services_dir.exists():
        for service_path in services_dir.iterdir():
            if service_path.is_dir():
                if has_python_files(service_path):
                    if not run_mypy(str(service_path)):
                        failed = True
                else:
                    print(f"Skipping {service_path.name} (no Python files)")
    return failed


def check_roots(project_root: Path) -> bool:
    """Check root modules."""
    failed = False
    for module in ROOT_MODULES:
        target = project_root / module
        if target.exists() and not run_mypy(str(target)):
            failed = True
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MyPy type checking.")
    parser.add_argument(
        "service",
        nargs="?",
        help="Optional service name to check (e.g., api-gateway).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    services_dir = project_root / "services"

    failed = False

    if args.service:
        # Check specific service
        target = services_dir / args.service
        if not target.exists():
            print(f"Error: Service '{args.service}' not found at {target}")
            sys.exit(1)
        if not run_mypy(str(target)):
            failed = True
    else:
        # Check all services and roots
        if check_services(services_dir):
            failed = True
        if check_roots(project_root):
            failed = True

    if failed:
        print("\nType checking failed.")
        sys.exit(1)
    else:
        print("\nAll type checks passed.")


if __name__ == "__main__":
    main()
