"""
Configuration for the pytest test suite.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Fixture to provide the project's root directory."""
    return Path(__file__).parent.parent
