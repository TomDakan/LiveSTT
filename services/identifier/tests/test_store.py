from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from identifier.store import LanceDBVoiceprintStore, StubVoiceprintStore


def _vec(seed: int = 0) -> np.ndarray:
    v = np.random.default_rng(seed).standard_normal(256).astype(np.float32)
    return v / np.linalg.norm(v)


# --- StubVoiceprintStore ---


def test_stub_identify_always_none() -> None:
    assert StubVoiceprintStore().identify(_vec()) is None


def test_stub_enroll_and_delete_are_nops() -> None:
    store = StubVoiceprintStore()
    store.enroll("Alice", _vec())  # should not raise
    store.delete("Alice")  # should not raise


# --- LanceDBVoiceprintStore ---


@patch("identifier.store.LANCEDB_AVAILABLE", False)
def test_lancedb_raises_when_unavailable() -> None:
    with pytest.raises(RuntimeError, match="lancedb"):
        LanceDBVoiceprintStore()


@patch("identifier.store.LANCEDB_AVAILABLE", True)
@patch("identifier.store.lancedb")
@patch("pathlib.Path.mkdir")
def test_lancedb_enroll_and_identify(
    mock_mkdir: MagicMock, mock_lancedb: MagicMock
) -> None:
    mock_table = MagicMock()
    mock_table.name = "voiceprints"
    mock_db = MagicMock()
    mock_db.table_names.return_value = ["voiceprints"]
    mock_db.open_table.return_value = mock_table
    mock_lancedb.connect.return_value = mock_db

    alice = _vec(0)
    store = LanceDBVoiceprintStore(db_path="/fake/db")
    store.enroll("Alice", alice)

    mock_table.delete.assert_called_with("id = 'Alice'")
    mock_table.add.assert_called_once()
    added = mock_table.add.call_args[0][0][0]
    assert added["id"] == "Alice"
    assert len(added["vector"]) == 256


@patch("identifier.store.LANCEDB_AVAILABLE", True)
@patch("identifier.store.lancedb")
@patch("pathlib.Path.mkdir")
def test_lancedb_identify_match(mock_mkdir: MagicMock, mock_lancedb: MagicMock) -> None:
    mock_table = MagicMock()
    mock_db = MagicMock()
    mock_db.table_names.return_value = ["voiceprints"]
    mock_db.open_table.return_value = mock_table
    mock_lancedb.connect.return_value = mock_db

    search_result = mock_table.search.return_value
    search_result.metric.return_value.limit.return_value.to_list.return_value = [
        {"id": "Alice", "vector": _vec(0).tolist(), "_distance": 0.1}
    ]

    store = LanceDBVoiceprintStore(db_path="/fake/db")
    result = store.identify(_vec(0))

    assert result is not None
    speaker, confidence = result
    assert speaker == "Alice"
    assert confidence == pytest.approx(0.9, abs=1e-3)


@patch("identifier.store.LANCEDB_AVAILABLE", True)
@patch("identifier.store.lancedb")
@patch("pathlib.Path.mkdir")
def test_lancedb_identify_no_match_above_threshold(
    mock_mkdir: MagicMock, mock_lancedb: MagicMock
) -> None:
    mock_table = MagicMock()
    mock_db = MagicMock()
    mock_db.table_names.return_value = ["voiceprints"]
    mock_db.open_table.return_value = mock_table
    mock_lancedb.connect.return_value = mock_db

    search_result = mock_table.search.return_value
    search_result.metric.return_value.limit.return_value.to_list.return_value = [
        {"id": "Bob", "_distance": 0.6}  # above default threshold of 0.25
    ]

    store = LanceDBVoiceprintStore(db_path="/fake/db")
    assert store.identify(_vec()) is None


@patch("identifier.store.LANCEDB_AVAILABLE", True)
@patch("identifier.store.lancedb")
@patch("pathlib.Path.mkdir")
def test_lancedb_identify_empty_store(
    mock_mkdir: MagicMock, mock_lancedb: MagicMock
) -> None:
    mock_table = MagicMock()
    mock_db = MagicMock()
    mock_db.table_names.return_value = ["voiceprints"]
    mock_db.open_table.return_value = mock_table
    mock_lancedb.connect.return_value = mock_db

    search_result = mock_table.search.return_value
    search_result.metric.return_value.limit.return_value.to_list.return_value = []

    store = LanceDBVoiceprintStore(db_path="/fake/db")
    assert store.identify(_vec()) is None
