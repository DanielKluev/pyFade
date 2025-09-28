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
WRONG_FILE = TEST_DATA_DIR / "results_2025-09-09T13-31-53.431753.json" # lm_eval format, not ShareGPT

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

def test_sharegpt_invalid_file() -> None:
    """Test handling of invalid file path."""
    invalid_path = TEST_DATA_DIR / "non_existent_file.json"
    data_format = ShareGPTFormat(invalid_path)
    with pytest.raises(FileNotFoundError):
        data_format.load()

def test_sharegpt_unsupported_format() -> None:
    """Test handling of unsupported file format."""
    data_format = ShareGPTFormat(WRONG_FILE)
    with pytest.raises(ValueError):
        data_format.load()

def test_sharegpt_save(tmp_path: pathlib.Path) -> None:
    """Test saving loaded ShareGPT data to a new file."""
    def check_saved_file(original_data: ShareGPTFormat, saved_file_path: pathlib.Path) -> None:
        assert saved_file_path.exists()
        # Load saved file and verify contents
        saved_data = ShareGPTFormat(saved_file_path)
        saved_data.load()
        assert len(saved_data.samples) == 10
        assert saved_data.samples[0].messages[0].content == original_data.samples[0].messages[0].content
        assert saved_data.samples[0].messages[1].content == original_data.samples[0].messages[1].content
        assert saved_data.samples[-1].messages[-1].content == original_data.samples[-1].messages[-1].content

    original_data = ShareGPTFormat(SHAREGPT_TEST_JSON)
    original_data.load()

    ## Test saving to JSONL
    jsonl_save_path = tmp_path / "saved_sharegpt.jsonl"
    original_data.save(jsonl_save_path)
    check_saved_file(original_data, jsonl_save_path)

    ## Test saving to JSON
    json_save_path = tmp_path / "saved_sharegpt.json"
    original_data.save(json_save_path)
    check_saved_file(original_data, json_save_path)

    ## Test saving to Parquet
    parquet_save_path = tmp_path / "saved_sharegpt.parquet"
    original_data.save(parquet_save_path)
    check_saved_file(original_data, parquet_save_path)

    ## Test saving to wrong format
    wrong_format_path = tmp_path / "saved_sharegpt.bin"
    with pytest.raises(ValueError):
        original_data.save(wrong_format_path)