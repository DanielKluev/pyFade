"""
Test suite for lm_eval_results data format handler.

Usable test data:
- gemma3:12b-u1 (tuned), GSM8K 3 docs:
    `tests/data/results_2025-09-09T13-31-53.431753.json`
    `tests/data/samples_gsm8k_2025-09-09T13-31-53.431753.jsonl`
- gemma3:12b-it-q4_K_M (base), GSM8K 3 docs:
    `tests/data/results_2025-09-09T13-42-42.857006.json`
    `tests/data/samples_gsm8k_2025-09-09T13-42-42.857006.jsonl`
- Expected: 1 shared success, 1 shared failure, 1 new failure in tuned model.
"""
import pathlib
import pytest
from py_fade.data_formats.lm_eval_results import LMEvalResult

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
LM_EVAL_TEST_RESULT_1 = TEST_DATA_DIR / "results_2025-09-09T13-31-53.431753.json"
LM_EVAL_TEST_RESULT_2 = TEST_DATA_DIR / "results_2025-09-09T13-42-42.857006.json"

def test_lm_eval_single_load() -> None:
    """Test loading of single lm_eval results file."""
    eval_result = LMEvalResult(LM_EVAL_TEST_RESULT_1)
    eval_result.load()
    assert eval_result.model_id == "gemma3:12b-u1"
    assert eval_result.origin_name == "gsm8k"
    assert len(eval_result.samples) == 3
    first_sample = eval_result.samples[0]
    assert "Question: A ship left a port and headed due west" in first_sample.prompt_text
    assert "The trains travel westward for 80 miles each" in first_sample.response_text

def test_lm_eval_compare() -> None:
    """Test comparison of two lm_eval results files."""
    eval_result_1 = LMEvalResult(LM_EVAL_TEST_RESULT_1)
    eval_result_1.load()
    eval_result_2 = LMEvalResult(LM_EVAL_TEST_RESULT_2)
    eval_result_2.load()

    comparison = eval_result_1.compare(eval_result_2)
    assert "shared_success" in comparison
    assert "shared_failure" in comparison
    assert "new_failure" in comparison
    assert "fixed" in comparison

    # Expected: 1 shared success, 1 shared failure, 1 new failure in tuned model.
    assert len(comparison["shared_success"]) == 1
    assert len(comparison["shared_failure"]) == 1
    assert len(comparison["new_failure"]) == 1
    assert len(comparison["fixed"]) == 0

    # Expected that failed sample is the one with "Claire makes a 3 egg omelet every morning" in prompt_text.
    failed_sample = comparison["new_failure"][0]
    assert "Claire makes a 3 egg omelet every morning" in failed_sample.prompt_text
