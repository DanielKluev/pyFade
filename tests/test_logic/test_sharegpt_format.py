"""
pytest tests for ShareGPT data format handling.

Usable test data:
- JSON:
  - `tests/data/sharegpt-structured-output-json_10.json`
- JSONL:
  - `tests/data/sharegpt-structured-output-json_10.jsonl`
- Parquet:
  - `tests/data/sharegpt-structured-output-json_10.parquet`

In each dataset, expected: 10 samples, each with 1 or more completions.
"""

import pathlib
import pytest
from py_fade.data_formats.share_gpt_format import ShareGPTFormat

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
SHAREGPT_TEST_JSON = TEST_DATA_DIR / "sharegpt-structured-output-json_10.json"
SHAREGPT_TEST_JSONL = TEST_DATA_DIR / "sharegpt-structured-output-json_10.jsonl"
SHAREGPT_TEST_PARQUET = TEST_DATA_DIR / "sharegpt-structured-output-json_10.parquet"

def run_shared_tests_for_load(data_format: ShareGPTFormat) -> None:
    """Run shared tests on loaded ShareGPT data format instance."""
    num_loaded = data_format.load()
    assert num_loaded == 10
    assert len(data_format.samples) == 10
    first_sample = data_format.samples[0]
    assert len(first_sample.messages) >= 2  # At least user and assistant messages
    assert first_sample.messages[0].role == "system"
    assert "You are a JSON generation assistant" in first_sample.messages[0].content
    assert first_sample.messages[1].role == "user"
    assert "Peer Review Framework for Predictive Analytics" in first_sample.messages[1].content

def test_sharegpt_load_json() -> None:
    """Test loading of ShareGPT JSON file."""
    data_format = ShareGPTFormat(SHAREGPT_TEST_JSON)
    assert data_format.format == "json"
    run_shared_tests_for_load(data_format)

def test_sharegpt_load_jsonl() -> None:
    """Test loading of ShareGPT JSONL file."""
    data_format = ShareGPTFormat(SHAREGPT_TEST_JSONL)
    assert data_format.format == "jsonl"
    run_shared_tests_for_load(data_format)

def test_sharegpt_load_parquet() -> None:
    """Test loading of ShareGPT Parquet file."""
    data_format = ShareGPTFormat(SHAREGPT_TEST_PARQUET)
    assert data_format.format == "parquet"
    run_shared_tests_for_load(data_format)
