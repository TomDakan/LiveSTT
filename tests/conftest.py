"""
Configuration for the pytest test suite.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
_ = load_dotenv()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Fixture to provide the project's root directory."""
    return Path(__file__).parent.parent
