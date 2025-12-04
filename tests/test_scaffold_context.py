"""Unit tests for scripts/scaffold_context.py"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts import scaffold_context


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    """
    Create a mock repository structure for testing.

    Should create:
    - tmp_path/pyproject.toml (root)
    - tmp_path/uv.lock (root)
    - tmp_path/services/service1/pyproject.toml
    - tmp_path/services/service2/pyproject.toml
    - tmp_path/libs/lib1/pyproject.toml

    Returns:
        Path: The temporary repository root
    """
    # Create the directory structure first
    (tmp_path / "services" / "service1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "services" / "service2").mkdir(parents=True, exist_ok=True)
    (tmp_path / "libs" / "lib1").mkdir(parents=True, exist_ok=True)

    # Now write the files
    _ = (tmp_path / "pyproject.toml").write_text("content")
    _ = (tmp_path / "uv.lock").write_text("content")
    _ = (tmp_path / "services" / "service1" / "pyproject.toml").write_text("content")
    _ = (tmp_path / "services" / "service2" / "pyproject.toml").write_text("content")
    _ = (tmp_path / "libs" / "lib1" / "pyproject.toml").write_text("content")

    return tmp_path


def test_creates_docker_context_directory(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that scaffold_docker_context creates the .docker-context/ directory.

    Hints:
    - Use monkeypatch.chdir(mock_repo) to change to the mock repo
    - Call scaffold_docker_context()
    - Assert that .docker-context/ directory exists
    """
    monkeypatch.chdir(mock_repo)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert (mock_repo / ".docker-context").exists()


def test_copies_root_pyproject_and_lock(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that root pyproject.toml and uv.lock are copied to .docker-context/.

    Hints:
    - Check that both files exist in .docker-context/
    - Optionally verify the content matches
    """
    monkeypatch.chdir(mock_repo)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert (mock_repo / ".docker-context" / "pyproject.toml").exists()
    assert (mock_repo / ".docker-context" / "uv.lock").exists()


def test_copies_service_pyprojects(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that service pyproject.toml files are copied with correct structure.

    Should verify:
    - .docker-context/services/service1/pyproject.toml exists
    - .docker-context/services/service2/pyproject.toml exists
    """
    monkeypatch.chdir(mock_repo)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert (
        mock_repo / ".docker-context" / "services" / "service1" / "pyproject.toml"
    ).exists()
    assert (
        mock_repo / ".docker-context" / "services" / "service2" / "pyproject.toml"
    ).exists()


def test_copies_lib_pyprojects(mock_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that library pyproject.toml files are copied with correct structure.

    Should verify:
    - .docker-context/libs/lib1/pyproject.toml exists
    """
    monkeypatch.chdir(mock_repo)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert (mock_repo / ".docker-context" / "libs" / "lib1" / "pyproject.toml").exists()


def test_handles_missing_root_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that the script handles missing root files gracefully.

    Create a repo WITHOUT pyproject.toml or uv.lock and verify:
    - Script doesn't crash
    - Warning messages are printed (optional: use capsys fixture)
    """
    monkeypatch.chdir(tmp_path)
    scaffold_context.scaffold_docker_context(tmp_path)
    # Directory should still be created
    assert (tmp_path / ".docker-context").exists()
    # But root files won't be copied
    assert not (tmp_path / ".docker-context" / "pyproject.toml").exists()
    assert not (tmp_path / ".docker-context" / "uv.lock").exists()


def test_cleans_existing_context(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that existing .docker-context/ is cleaned before creating new one.

    Steps:
    1. Create .docker-context/ with some old files
    2. Run scaffold_docker_context()
    3. Verify old files are gone and new structure exists
    """
    monkeypatch.chdir(mock_repo)
    _ = (mock_repo / ".docker-context").mkdir(parents=True, exist_ok=True)
    _ = (mock_repo / ".docker-context" / "old_file.txt").write_text("content")
    scaffold_context.scaffold_docker_context(mock_repo)
    assert not (mock_repo / ".docker-context" / "old_file.txt").exists()
    assert (mock_repo / ".docker-context" / "pyproject.toml").exists()
    assert (mock_repo / ".docker-context" / "uv.lock").exists()
    assert (
        mock_repo / ".docker-context" / "services" / "service1" / "pyproject.toml"
    ).exists()
    assert (
        mock_repo / ".docker-context" / "services" / "service2" / "pyproject.toml"
    ).exists()
    assert (mock_repo / ".docker-context" / "libs" / "lib1" / "pyproject.toml").exists()


def test_ignores_non_directory_items_in_services(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that files (not directories) in services/ are ignored.

    Create:
    - services/README.md (file, should be ignored)
    - services/service1/ (directory, should be processed)
    """
    monkeypatch.chdir(mock_repo)
    _ = (mock_repo / "services" / "README.md").write_text("content")
    _ = (mock_repo / "services" / "service1" / "pyproject.toml").write_text("content")
    scaffold_context.scaffold_docker_context(mock_repo)
    assert not (mock_repo / ".docker-context" / "services" / "README.md").exists()
    assert (
        mock_repo / ".docker-context" / "services" / "service1" / "pyproject.toml"
    ).exists()


def test_handles_services_without_pyproject(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that services without pyproject.toml are skipped gracefully.

    Create:
    - services/incomplete-service/ (directory but no pyproject.toml)
    - Verify it doesn't appear in .docker-context/
    """
    monkeypatch.chdir(mock_repo)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert not (
        mock_repo / ".docker-context" / "services" / "incomplete-service"
    ).exists()


# BONUS CHALLENGE (Optional):
def test_preserves_file_metadata(
    mock_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that shutil.copy2 preserves file metadata (timestamps, etc.).

    This is advanced - only attempt if you want extra practice!
    Hint: Check os.stat() before and after copying
    """
    monkeypatch.chdir(mock_repo)
    _ = (mock_repo / "services" / "incomplete-service").mkdir(parents=True, exist_ok=True)
    scaffold_context.scaffold_docker_context(mock_repo)
    assert not (
        mock_repo / ".docker-context" / "services" / "incomplete-service"
    ).exists()
