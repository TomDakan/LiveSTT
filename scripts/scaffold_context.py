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


def _copy_file_if_exists(source: Path, dest: Path, repo_root: Path) -> None:
    """Copy a file if it exists, with status message."""
    if source.exists():
        shutil.copy2(source, dest)
        print(f"✅ Copied {source.relative_to(repo_root)}")
    else:
        print(f"⚠️  Warning: {source} not found")


def _copy_workspace_pyprojects(
    workspace_dir: Path, docker_context: Path, workspace_name: str
) -> None:
    """Copy pyproject.toml files from a workspace directory (services/ or libs/)."""
    if not workspace_dir.exists():
        return

    for item_path in workspace_dir.iterdir():
        if not item_path.is_dir():
            continue

        pyproject = item_path / "pyproject.toml"
        if not pyproject.exists():
            continue

        # Create workspace/<name>/ in docker-context
        dest_dir = docker_context / workspace_name / item_path.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyproject, dest_dir / "pyproject.toml")
        print(f"✅ Copied {workspace_name}/{item_path.name}/pyproject.toml")


def scaffold_docker_context(repo_root: Path | None = None) -> None:
    """Create .docker-context/ with files needed for Docker builds."""
    # Define paths
    repo_root = repo_root or Path(__file__).parent.parent
    docker_context = repo_root / ".docker-context"

    # Clean existing context
    if docker_context.exists():
        shutil.rmtree(docker_context)

    # Create fresh context directory
    docker_context.mkdir(parents=True, exist_ok=True)

    # Copy root workspace files
    _copy_file_if_exists(
        repo_root / "pyproject.toml", docker_context / "pyproject.toml", repo_root
    )
    _copy_file_if_exists(repo_root / "uv.lock", docker_context / "uv.lock", repo_root)

    # Copy service and library pyproject.toml files
    _copy_workspace_pyprojects(repo_root / "services", docker_context, "services")
    _copy_workspace_pyprojects(repo_root / "libs", docker_context, "libs")

    print(f"\n✨ Docker build context scaffolded at: {docker_context}")


if __name__ == "__main__":
    scaffold_docker_context()
