"""Tests for the configuration module."""


# --- Tests for typed-settings ---
import os
from pathlib import Path

import pytest
import typed_settings as ts


from live_stt import config

@pytest.fixture
def patch_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Override the PROJECT_ROOT to point to a temp dir."""
    # Create a dummy .env file in the temp path
    env_file = tmp_path / ".env"
    env_file.write_text("LIVE_STT_LOG_LEVEL=DEBUG\n")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    return tmp_path

def test_typed_settings_load(patch_project_root: Path) -> None:
    """Test that settings are loaded correctly from the .env file."""
    # Reload settings to pick up the patched root
    settings = ts.load_settings(config.Settings)
    assert settings.log_level == "DEBUG"

def test_typed_settings_load_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override defaults."""
    monkeypatch.setenv("LIVE_STT_LOG_LEVEL", "WARNING")

    # Reload settings to pick up the env var
    settings = ts.load_settings(config.Settings)
    assert settings.log_level == "WARNING"

