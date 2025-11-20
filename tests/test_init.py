"""
Initial tests for the live-stt project.
"""

from pathlib import Path


def test_project_structure(project_root: Path) -> None:
    """Tests that the project structure is as expected."""
    assert (project_root / "pyproject.toml").is_file()
    assert (project_root / "src" / "live_stt").is_dir()
