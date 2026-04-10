"""Regression tests ensuring API keys never leak into logs or repr."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SECRET_KEY = "sk-test-secret-key-SHOULD-NOT-APPEAR-12345"


@pytest.mark.asyncio
async def test_deepgram_api_key_not_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Instantiating the adapter must not log the API key."""
    from stt_provider.deepgram_adapter import DeepgramTranscriber

    with caplog.at_level("DEBUG"):
        _ = DeepgramTranscriber(api_key=SECRET_KEY)

    full_log = " ".join(r.message for r in caplog.records)
    assert SECRET_KEY not in full_log


def test_source_no_key_in_log_calls() -> None:
    """Static scan: no log/print statement references ``api_key``."""
    src_dir = Path(__file__).resolve().parents[1] / "src"
    # Matches logger.xxx(...api_key...) or print(...api_key...)
    pattern = re.compile(
        r"(logger\.\w+|print)\s*\(.*\bapi_key\b", re.IGNORECASE
    )
    violations: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        for i, line in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), 1
        ):
            if pattern.search(line):
                violations.append(f"{py_file.name}:{i}: {line.strip()}")

    assert violations == [], (
        "Found api_key in log/print calls:\n"
        + "\n".join(violations)
    )
