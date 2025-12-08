"""
Cross-platform script to run type checking (MyPy and BasedPyright).
Usage:
    python scripts/type_check.py [service_name]

If service_name is provided, runs checks for that service.
If not, runs checks for all services and root modules.
"""

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

# Define root modules to check
ROOT_MODULES = ["src", "scripts", "bootstrap.py"]


def run_command(cmd: list[str], task_name: str) -> bool:
    """Run a type checking command and return True if successful."""
    print(f"Running {task_name}...")
    try:
        result = subprocess.run(
            cmd,
            check=False,
            shell=False,
        )  # nosec B603
        if result.returncode != 0:
            print(f"FAILED: {task_name}")
            return False
        return True
    except Exception as e:
        print(f"Error running {task_name}: {e}")
        return False


def run_checks(target: str) -> bool:
    """Run both MyPy and BasedPyright on the target."""
    # 1. MyPy
    mypy_cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--no-incremental",
        "--no-warn-unused-configs",
        target,
    ]
    mypy_ok = run_command(mypy_cmd, f"MyPy on {target}")

    # 2. BasedPyright
    # Run via python module (-m) to ensure we use the venv's installed package.
    basedpyright_cmd = [
        sys.executable,
        "-m",
        "basedpyright",
        target,
    ]
    bpy_ok = run_command(basedpyright_cmd, f"BasedPyright on {target}")

    return mypy_ok and bpy_ok


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
                    if not run_checks(str(service_path)):
                        failed = True
                else:
                    print(f"Skipping {service_path.name} (no Python files)")
    return failed


def check_roots(project_root: Path) -> bool:
    """Check root modules."""
    failed = False
    for module in ROOT_MODULES:
        target = project_root / module
        if target.exists():
            # Skip directories without Python files
            if target.is_dir() and not has_python_files(target):
                print(f"Skipping {module} (no Python files)")
                continue
            if not run_checks(str(target)):
                failed = True
    return failed


class TypeCheckArgs(argparse.Namespace):
    service: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run type checking.")
    _ = parser.add_argument(
        "service",
        nargs="?",
        help="Optional service name to check (e.g., api-gateway).",
    )
    # Parse into a typed namespace
    args = parser.parse_args(namespace=TypeCheckArgs())

    project_root = Path(__file__).resolve().parent.parent
    services_dir = project_root / "services"

    failed = False

    if args.service:
        # Check specific service
        service_name = args.service
        target = services_dir / service_name
        if not target.exists():
            print(f"Error: Service '{service_name}' not found at {target}")
            sys.exit(1)
        if not run_checks(str(target)):
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
