#!/usr/bin/env python3
"""
Scaffold Docker Build Context

This script creates a `.docker-context/` directory containing only the files
needed for Docker dependency layer caching:
- Root `uv.lock` and `pyproject.toml`
- Service `pyproject.toml` files (from services/*/)
- Library `pyproject.toml` files (from libs/*/)

This enables cross-platform Docker builds without complex shell commands.

Usage:
    python scripts/scaffold_context.py
"""

from __future__ import annotations

import shutil
from pathlib import Path


def scaffold_docker_context() -> None:
    """Create .docker-context/ with files needed for Docker builds."""
    # Define paths
    repo_root = Path(__file__).parent.parent
    docker_context = repo_root / ".docker-context"

    # Clean existing context
    if docker_context.exists():
        shutil.rmtree(docker_context)

    # Create fresh context directory
    docker_context.mkdir(parents=True, exist_ok=True)

    # Copy root workspace files
    root_pyproject = repo_root / "pyproject.toml"
    root_lock = repo_root / "uv.lock"

    if root_pyproject.exists():
        shutil.copy2(root_pyproject, docker_context / "pyproject.toml")
        print(f"✅ Copied {root_pyproject.relative_to(repo_root)}")
    else:
        print(f"⚠️  Warning: {root_pyproject} not found")

    if root_lock.exists():
        shutil.copy2(root_lock, docker_context / "uv.lock")
        print(f"✅ Copied {root_lock.relative_to(repo_root)}")
    else:
        print(f"⚠️  Warning: {root_lock} not found")

    # Copy service pyproject.toml files
    services_dir = repo_root / "services"
    if services_dir.exists():
        for service_path in services_dir.iterdir():
            if service_path.is_dir():
                service_pyproject = service_path / "pyproject.toml"
                if service_pyproject.exists():
                    # Create services/<name>/ in docker-context
                    dest_dir = docker_context / "services" / service_path.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(
                        service_pyproject, dest_dir / "pyproject.toml"
                    )
                    print(
                        f"✅ Copied services/{service_path.name}/pyproject.toml"
                    )

    # Copy library pyproject.toml files
    libs_dir = repo_root / "libs"
    if libs_dir.exists():
        for lib_path in libs_dir.iterdir():
            if lib_path.is_dir():
                lib_pyproject = lib_path / "pyproject.toml"
                if lib_pyproject.exists():
                    # Create libs/<name>/ in docker-context
                    dest_dir = docker_context / "libs" / lib_path.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(lib_pyproject, dest_dir / "pyproject.toml")
                    print(f"✅ Copied libs/{lib_path.name}/pyproject.toml")

    print(f"\n✨ Docker build context scaffolded at: {docker_context}")


if __name__ == "__main__":
    scaffold_docker_context()
