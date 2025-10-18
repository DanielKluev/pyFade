"""
Test DPO export functionality.

Tests the export controller's DPO export flow including pair generation,
template handling, and JSONL output.
"""
from __future__ import annotations

import pathlib
import tempfile
import json

from py_fade.controllers.export_controller import ExportController
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from tests.helpers.data_helpers import create_test_sample_with_completion


def test_dpo_export_basic(app_with_dataset, temp_dataset):
    """
    Test basic DPO export with one sample generating one pair.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with two completions: one high-rated (chosen), one low-rated (rejected)
    sample1, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2,
                                                              title="Sample 1", completion_text="Good answer",
                                                              model_id=mapped_model.model_id)

    # Add second completion (rejected)
    from tests.helpers.data_helpers import create_test_completion_with_params, create_test_logprobs  # pylint: disable=import-outside-toplevel
    from py_fade.dataset.completion_rating import PromptCompletionRating  # pylint: disable=import-outside-toplevel
    completion2 = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="b" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)
    temp_dataset.commit()

    # Create DPO export template
    template = ExportTemplate.create(
        temp_dataset,
        name="Test DPO Template",
        description="Test DPO export",
        training_type="DPO",
        output_format="JSONL (Anthropic)",
        model_families=["Llama3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "percentage",
            "limit_value": 100,
            "order": "random"
        }],
    )
    temp_dataset.commit()

    # Export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        pairs_count = export_controller.run_export()

        # Should export 1 pair
        assert pairs_count == 1
        assert export_controller.export_results is not None
        assert export_controller.export_results.total_exported == 1

        # Check file content
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1

            pair = json.loads(lines[0])
            assert "prompt" in pair
            assert "chosen" in pair
            assert "rejected" in pair
            assert pair["chosen"] == "Good answer"
            assert pair["rejected"] == "Bad answer"
            assert pair["prompt"] == "Test prompt"  # Simple template just returns user message

    finally:
        temp_path.unlink(missing_ok=True)


def test_dpo_export_multiple_pairs(app_with_dataset, temp_dataset):
    """
    Test DPO export with multiple samples generating multiple pairs.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create two samples, each with chosen and rejected completions
    from tests.helpers.data_helpers import create_test_completion_with_params, create_test_logprobs  # pylint: disable=import-outside-toplevel
    from py_fade.dataset.completion_rating import PromptCompletionRating  # pylint: disable=import-outside-toplevel

    # Sample 1
    sample1, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2,
                                                              title="Sample 1", completion_text="Good answer 1",
                                                              model_id=mapped_model.model_id)
    completion2 = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="b" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer 1")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    # Sample 2
    sample2, _ = create_test_sample_with_completion(temp_dataset, facet, rating=8, min_logprob=-0.4, avg_logprob=-0.2,
                                                              title="Sample 2", prompt_text="Another prompt",
                                                              completion_text="Good answer 2", model_id=mapped_model.model_id)
    completion4 = create_test_completion_with_params(temp_dataset, sample2.prompt_revision, sha256="d" * 64, model_id=mapped_model.model_id,
                                                     completion_text="Bad answer 2")
    PromptCompletionRating.set_rating(temp_dataset, completion4, facet, 4)
    create_test_logprobs(temp_dataset, completion4.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)
    temp_dataset.commit()

    # Create DPO export template
    template = ExportTemplate.create(
        temp_dataset,
        name="Test DPO Template",
        description="Test DPO export",
        training_type="DPO",
        output_format="JSONL (Anthropic)",
        model_families=["Llama3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "percentage",
            "limit_value": 100,
            "order": "random"
        }],
    )
    temp_dataset.commit()

    # Export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        pairs_count = export_controller.run_export()

        # Should export 2 pairs (one per sample)
        assert pairs_count == 2

        # Check file content
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 2

            pair1 = json.loads(lines[0])
            pair2 = json.loads(lines[1])

            # Check that we have both samples' data
            prompts = {pair1["prompt"], pair2["prompt"]}
            assert "Test prompt" in prompts
            assert "Another prompt" in prompts

            chosen_texts = {pair1["chosen"], pair2["chosen"]}
            assert "Good answer 1" in chosen_texts or "Good answer 2" in chosen_texts

    finally:
        temp_path.unlink(missing_ok=True)


def test_dpo_export_with_sample_limit(app_with_dataset, temp_dataset):
    """
    Test DPO export respects sample limits.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create three samples with valid DPO pairs
    from tests.helpers.data_helpers import create_test_completion_with_params, create_test_logprobs  # pylint: disable=import-outside-toplevel
    from py_fade.dataset.completion_rating import PromptCompletionRating  # pylint: disable=import-outside-toplevel

    for i in range(3):
        sample, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2,
                                                                 title=f"Sample {i+1}", prompt_text=f"Prompt {i+1}",
                                                                 completion_text=f"Good answer {i+1}", model_id=mapped_model.model_id)
        completion2 = create_test_completion_with_params(temp_dataset, sample.prompt_revision, sha256=f"{i:064x}",
                                                         model_id=mapped_model.model_id, completion_text=f"Bad answer {i+1}")
        PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 5)
        create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    temp_dataset.commit()

    # Create DPO export template with limit of 2 samples
    template = ExportTemplate.create(
        temp_dataset,
        name="Test DPO Template",
        description="Test DPO export with limit",
        training_type="DPO",
        output_format="JSONL (Anthropic)",
        model_families=["Llama3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "count",
            "limit_value": 2,
            "order": "random"
        }],
    )
    temp_dataset.commit()

    # Export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        pairs_count = export_controller.run_export()

        # Should export only 2 pairs (limit of 2 samples)
        assert pairs_count == 2

    finally:
        temp_path.unlink(missing_ok=True)


def test_dpo_export_no_eligible_pairs(app_with_dataset, temp_dataset):
    """
    Test DPO export raises error when no eligible pairs found.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with only one completion (can't form pair)
    create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2, title="Sample 1",
                                       completion_text="Only answer", model_id=mapped_model.model_id)
    temp_dataset.commit()

    # Create DPO export template
    template = ExportTemplate.create(
        temp_dataset,
        name="Test DPO Template",
        description="Test DPO export",
        training_type="DPO",
        output_format="JSONL (Anthropic)",
        model_families=["Llama3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "percentage",
            "limit_value": 100,
            "order": "random"
        }],
    )
    temp_dataset.commit()

    # Export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = pathlib.Path(f.name)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)

        # Should raise error because no pairs can be formed
        try:
            export_controller.run_export()
            assert False, "Expected ValueError to be raised"
        except ValueError as e:
            assert "No eligible DPO pairs found" in str(e)

    finally:
        temp_path.unlink(missing_ok=True)
