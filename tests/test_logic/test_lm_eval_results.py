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

MMLU Pro Plus test data:
- gemma3_12b_u2 (tuned):
    `tests/data/eval_mmlu_pro_plus/results_2025-10-14T14-44-39.372006.json`
    Multiple samples files for chemistry, health, psychology subsets
- gemma-3-12b-it-base (base):
    `tests/data/eval_mmlu_pro_plus/results_2025-10-14T15-11-56.507865.json`
    Multiple samples files for chemistry, health, psychology subsets
- Expected: 3 subsets × 3 samples each = 9 samples total
"""
import pathlib
import pytest
from py_fade.data_formats.lm_eval_results import LMEvalResult
from py_fade.providers.llm_templates import (strip_template_gemma3, strip_template_qwen3, strip_template_llama3, strip_template_mistral,
                                             strip_chat_template)

TEST_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
LM_EVAL_TEST_RESULT_1 = TEST_DATA_DIR / "results_2025-09-09T13-31-53.431753.json"
LM_EVAL_TEST_RESULT_2 = TEST_DATA_DIR / "results_2025-09-09T13-42-42.857006.json"

MMLU_DATA_DIR = TEST_DATA_DIR / "eval_mmlu_pro_plus"
MMLU_TUNED_RESULT = MMLU_DATA_DIR / "results_2025-10-14T14-44-39.372006.json"
MMLU_BASE_RESULT = MMLU_DATA_DIR / "results_2025-10-14T15-11-56.507865.json"


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


def test_lm_eval_save_raises_not_implemented():
    """Test that save() method raises NotImplementedError as expected."""
    eval_result = LMEvalResult(LM_EVAL_TEST_RESULT_1)

    with pytest.raises(NotImplementedError, match="read-only and does not support saving"):
        eval_result.save()

    with pytest.raises(NotImplementedError, match="read-only and does not support saving"):
        eval_result.save("/some/path")


def test_lm_eval_mmlu_load_multiple_samples_files() -> None:
    """Test loading MMLU results with multiple sample files (split subsets)."""
    eval_result = LMEvalResult(MMLU_TUNED_RESULT)
    eval_result.load()

    # Should load all samples from chemistry, health, and psychology subsets
    # Each subset has 3 samples, total 9 samples
    assert len(eval_result.samples) == 9, f"Expected 9 samples, got {len(eval_result.samples)}"

    # Check that samples from different subsets are present
    # Chemistry has question about "unknown substance" with "high melting point"
    chemistry_samples = [s for s in eval_result.samples if "high melting point" in s.prompt_text]
    assert len(chemistry_samples) > 0, "No chemistry samples found"

    # Health has question about "Bronchial breathing"
    health_samples = [s for s in eval_result.samples if "Bronchial breathing" in s.prompt_text]
    assert len(health_samples) > 0, "No health samples found"


def test_lm_eval_mmlu_model_id_extraction() -> None:
    """Test correct model ID parsing from MMLU results files."""
    tuned_result = LMEvalResult(MMLU_TUNED_RESULT)
    tuned_result.load()
    # Model name in file is "/workspace/gemma3_12b_u2", should extract "gemma3_12b_u2"
    assert tuned_result.model_id == "gemma3_12b_u2", f"Expected 'gemma3_12b_u2', got '{tuned_result.model_id}'"

    base_result = LMEvalResult(MMLU_BASE_RESULT)
    base_result.load()
    # Model name in file is "/workspace/gemma-3-12b-it-base", should extract "gemma-3-12b-it-base"
    assert base_result.model_id == "gemma-3-12b-it-base", f"Expected 'gemma-3-12b-it-base', got '{base_result.model_id}'"


def test_lm_eval_mmlu_prompt_text_stripped() -> None:
    """Test that prompt text is correctly extracted with chat template tokens stripped."""
    eval_result = LMEvalResult(MMLU_TUNED_RESULT)
    eval_result.load()

    # All samples should have prompts without chat template tokens
    for sample in eval_result.samples:
        # Should NOT contain Gemma3 template tokens
        assert "<bos>" not in sample.prompt_text, f"Found <bos> in prompt: {sample.prompt_text[:100]}"
        assert "<start_of_turn>" not in sample.prompt_text, f"Found <start_of_turn> in prompt: {sample.prompt_text[:100]}"
        assert "<end_of_turn>" not in sample.prompt_text, f"Found <end_of_turn> in prompt: {sample.prompt_text[:100]}"

        # Should contain actual question content
        assert len(sample.prompt_text) > 100, "Prompt text seems too short"


def test_lm_eval_mmlu_compare_paired_filtering() -> None:
    """Test paired filtering on MMLU data showing new failures in tuned model vs base."""
    tuned_result = LMEvalResult(MMLU_TUNED_RESULT)
    tuned_result.load()
    base_result = LMEvalResult(MMLU_BASE_RESULT)
    base_result.load()

    # Compare tuned to base (tuned is current, base is baseline)
    # This should show samples that failed in tuned but succeeded in base (regressions)
    comparison = tuned_result.compare(base_result)

    # According to the data analysis:
    # - Chemistry: 1 sample goes from base=1.0 to tuned=0.0 → new failure (regression)
    # - Health: 1 sample goes from base=1.0 to tuned=0.0 → new failure (regression)
    # - Psychology: 1 sample goes from base=1.0 to tuned=0.0 → new failure (regression)
    # Total: 3 new failures (regressions in tuned model)
    assert len(comparison["new_failure"]) == 3, f"Expected 3 new failures, got {len(comparison['new_failure'])}"

    # Should also have shared successes and shared failures
    assert len(comparison["shared_success"]) == 3, "Expected 3 shared successes"
    assert len(comparison["shared_failure"]) == 3, "Expected 3 shared failures"

    # No fixes expected (tuned performs worse than base)
    assert len(comparison["fixed"]) == 0, f"Expected 0 fixes, got {len(comparison['fixed'])}"


def test_strip_template_gemma3() -> None:
    """Test Gemma3 template token stripping."""
    templated = "<bos><start_of_turn>user\nHello world<end_of_turn>\n<start_of_turn>model\n"
    stripped = strip_template_gemma3(templated)
    assert stripped == "Hello world"
    assert "<bos>" not in stripped
    assert "<start_of_turn>" not in stripped
    assert "<end_of_turn>" not in stripped


def test_strip_template_qwen3() -> None:
    """Test Qwen3 template token stripping."""
    templated = "<|im_start|>user\nHello world<|im_end|>\n<|im_start|>assistant\n"
    stripped = strip_template_qwen3(templated)
    assert stripped == "Hello world"
    assert "<|im_start|>" not in stripped
    assert "<|im_end|>" not in stripped


def test_strip_template_llama3() -> None:
    """Test Llama3 template token stripping."""
    templated = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nHello world<|eot_id|>"
    stripped = strip_template_llama3(templated)
    assert stripped == "Hello world"
    assert "<|begin_of_text|>" not in stripped
    assert "<|start_header_id|>" not in stripped
    assert "<|eot_id|>" not in stripped


def test_strip_template_mistral() -> None:
    """Test Mistral template token stripping."""
    templated = "[INST] Hello world [/INST] Response here</s>"
    stripped = strip_template_mistral(templated)
    assert "Hello world" in stripped
    assert "Response here" in stripped
    assert "[INST]" not in stripped
    assert "[/INST]" not in stripped
    assert "</s>" not in stripped


def test_strip_chat_template_auto_detect() -> None:
    """Test automatic template detection and stripping."""
    # Test Gemma3 auto-detection
    gemma_text = "<bos><start_of_turn>user\nTest<end_of_turn>\n"
    assert strip_chat_template(gemma_text) == "Test"

    # Test Qwen3 auto-detection
    qwen_text = "<|im_start|>user\nTest<|im_end|>\n"
    assert strip_chat_template(qwen_text) == "Test"

    # Test with model_id hint
    gemma_with_hint = "<bos><start_of_turn>user\nTest<end_of_turn>\n"
    assert strip_chat_template(gemma_with_hint, "gemma3-12b") == "Test"

    # Test plain text (no template)
    plain_text = "This is plain text without templates"
    assert strip_chat_template(plain_text) == plain_text


def test_strip_chat_template_complex_content() -> None:
    """Test template stripping with complex multi-turn content."""
    # Complex Gemma3 prompt with multiple turns (like MMLU few-shot examples)
    complex_prompt = """<bos><start_of_turn>user
The following are multiple choice questions about chemistry.

Question: What is H2O?
Options:
A. Hydrogen
B. Water
C. Oxygen
Answer: The answer is (B).

Question: What is CO2?<end_of_turn>
<start_of_turn>model
"""

    stripped = strip_template_gemma3(complex_prompt)
    # Should contain the question content
    assert "multiple choice questions" in stripped
    assert "What is H2O?" in stripped
    assert "What is CO2?" in stripped
    # Should not contain template tokens
    assert "<bos>" not in stripped
    assert "<start_of_turn>" not in stripped
    assert "<end_of_turn>" not in stripped
