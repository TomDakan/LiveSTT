"""
Configuration for the pytest test suite.
"""

import os
import tomllib
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
_ = load_dotenv()

# Fall back to mise.local.toml [env] section for local secrets (e.g. DEEPGRAM_API_KEY).
# mise exports these into the shell, but subprocesses spawned with -NoProfile don't
# inherit them. Only sets vars not already present in the environment.
_mise_local = Path(__file__).parent.parent / "mise.local.toml"
if _mise_local.exists():
    with _mise_local.open("rb") as _f:
        _mise_env = tomllib.load(_f).get("env", {})
    for _k, _v in _mise_env.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Fixture to provide the project's root directory."""
    return Path(__file__).parent.parent
