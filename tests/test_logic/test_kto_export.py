"""
Test KTO export functionality.

Tests the export controller's KTO export flow including sample generation,
label assignment, and JSONL output.
"""
from __future__ import annotations

import json

from py_fade.controllers.export_controller import ExportController
from py_fade.controllers.kto_controller import KTOController
from py_fade.dataset.facet import Facet
from py_fade.dataset.completion_rating import PromptCompletionRating
from tests.helpers.data_helpers import (create_test_sample_with_completion, create_test_completion_with_params, create_test_logprobs,
                                        create_export_template_and_setup, setup_export_test_with_facet_and_model,
                                        create_sample_with_good_completion, run_export_expecting_error)


def test_kto_controller_basic(app_with_dataset, temp_dataset):
    """
    Test KTO controller generates correct good and bad samples.
    """
    # Create facet with min_rating=7, max_rating=5 and get mock model
    facet, mapped_model = setup_export_test_with_facet_and_model(app_with_dataset, temp_dataset, min_rating=7, max_rating=5)

    # Create sample with three completions: good (rating=9), bad (rating=3), neutral (rating=6)
    sample1, _ = create_sample_with_good_completion(temp_dataset, facet, mapped_model.model_id, title="Sample 1",
                                                    completion_text="Good answer")

    # Add bad completion
    comp_bad = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="b" * 64, model_id=mapped_model.model_id,
                                                  completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, comp_bad, facet, 3)
    create_test_logprobs(temp_dataset, comp_bad.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    # Add neutral completion (should not be exported)
    comp_neutral = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="c" * 64,
                                                      model_id=mapped_model.model_id, completion_text="Neutral answer")
    PromptCompletionRating.set_rating(temp_dataset, comp_neutral, facet, 6)
    create_test_logprobs(temp_dataset, comp_neutral.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)

    temp_dataset.commit()

    # Test KTO controller
    kto_controller = KTOController(temp_dataset, facet, mapped_model.model_id)
    result = kto_controller.generate_samples_for_sample(sample1)

    # Should generate 2 samples: 1 good, 1 bad (neutral is skipped)
    assert len(result.samples) == 2
    assert len(result.failure_reasons) == 0

    # Check labels
    good_samples = [s for s in result.samples if s.label is True]
    bad_samples = [s for s in result.samples if s.label is False]

    assert len(good_samples) == 1
    assert len(bad_samples) == 1
    assert good_samples[0].completion == "Good answer"
    assert bad_samples[0].completion == "Bad answer"


def test_kto_export_basic(app_with_dataset, temp_dataset):
    """
    Test basic KTO export with one sample generating good and bad samples.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, max_rating=5, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with two completions: one good, one bad
    sample1, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2, title="Sample 1",
                                                    completion_text="Good answer", model_id=mapped_model.model_id)

    # Add bad completion
    comp_bad = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="b" * 64, model_id=mapped_model.model_id,
                                                  completion_text="Bad answer")
    PromptCompletionRating.set_rating(temp_dataset, comp_bad, facet, 3)
    create_test_logprobs(temp_dataset, comp_bad.id, mapped_model.model_id, min_logprob=-0.45, avg_logprob=-0.25)
    temp_dataset.commit()

    # Create KTO export template
    template, temp_path = create_export_template_and_setup(temp_dataset, facet, "KTO", "JSONL (TRL)", ["Llama3"])

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        samples_count = export_controller.run_export()

        # Should export 2 samples (1 good, 1 bad)
        assert samples_count == 2
        assert export_controller.export_results is not None
        assert export_controller.export_results.total_exported == 2

        # Check file content
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 2

            # Parse both samples
            sample1_json = json.loads(lines[0])
            sample2_json = json.loads(lines[1])

            # Check structure
            for sample_json in [sample1_json, sample2_json]:
                assert "prompt" in sample_json
                assert "completion" in sample_json
                assert "label" in sample_json
                assert isinstance(sample_json["prompt"], list)
                assert isinstance(sample_json["completion"], list)
                assert isinstance(sample_json["label"], bool)

            # One should be good (label=true), one should be bad (label=false)
            labels = [sample1_json["label"], sample2_json["label"]]
            assert True in labels
            assert False in labels

            # Check completions match
            completions = []
            for sample_json in [sample1_json, sample2_json]:
                assert len(sample_json["completion"]) == 1
                assert sample_json["completion"][0]["role"] == "assistant"
                completions.append(sample_json["completion"][0]["content"])

            assert "Good answer" in completions
            assert "Bad answer" in completions

    finally:
        temp_path.unlink(missing_ok=True)


def test_kto_export_threshold_override(app_with_dataset, temp_dataset):
    """
    Test KTO export with template threshold overrides.
    """
    # Create facet with default thresholds
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, max_rating=5, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with rating=6 (neutral with default thresholds)
    _ = create_test_sample_with_completion(temp_dataset, facet, rating=6, min_logprob=-0.4, avg_logprob=-0.2, title="Sample 1",
                                           completion_text="Neutral answer", model_id=mapped_model.model_id)
    temp_dataset.commit()

    # Create KTO export template with overridden max_rating=6 (making rating=6 "bad")
    template, temp_path = create_export_template_and_setup(temp_dataset, facet, "KTO", "JSONL (TRL)", ["Llama3"],
                                                           facet_overrides={"max_rating": 6})

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        samples_count = export_controller.run_export()

        # Should export 1 sample (marked as bad due to threshold override)
        assert samples_count == 1

        # Check file content
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1

            sample_json = json.loads(lines[0])
            assert sample_json["label"] is False  # Should be marked as bad
            assert sample_json["completion"][0]["content"] == "Neutral answer"

    finally:
        temp_path.unlink(missing_ok=True)


def test_kto_export_no_eligible_samples(app_with_dataset, temp_dataset):
    """
    Test KTO export raises error when no eligible samples found.
    """
    # Create facet and get mock model
    facet, mapped_model = setup_export_test_with_facet_and_model(app_with_dataset, temp_dataset, min_rating=7, max_rating=5)

    # Create sample with only neutral rating (rating=6)
    _ = create_test_sample_with_completion(temp_dataset, facet, rating=6, min_logprob=-0.4, avg_logprob=-0.2, title="Sample 1",
                                           completion_text="Neutral answer", model_id=mapped_model.model_id)
    temp_dataset.commit()

    # Create KTO export template
    template, temp_path = create_export_template_and_setup(temp_dataset, facet, "KTO", "JSONL (TRL)", ["Llama3"])

    try:
        run_export_expecting_error(app_with_dataset, temp_dataset, template, temp_path, "No eligible KTO samples found",
                                   mapped_model.model_id)

    finally:
        temp_path.unlink(missing_ok=True)


def test_kto_export_with_sample_limit(app_with_dataset, temp_dataset):
    """
    Test KTO export respects sample limit.
    """
    # Create facet
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, max_rating=5, min_logprob_threshold=-0.5,
                         avg_logprob_threshold=-0.3)
    temp_dataset.commit()

    # Get mock model
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create 3 samples with good completions (each with unique prompt)
    for i in range(3):
        create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.4, avg_logprob=-0.2, title=f"Sample {i+1}",
                                           prompt_text=f"Test prompt {i+1}", completion_text=f"Good answer {i+1}",
                                           model_id=mapped_model.model_id)
    temp_dataset.commit()

    # Create KTO export template with limit of 2 samples
    template, temp_path = create_export_template_and_setup(temp_dataset, facet, "KTO", "JSONL (TRL)", ["Llama3"], limit_type="count",
                                                           limit_value=2)

    try:
        export_controller = ExportController(app_with_dataset, temp_dataset, template, target_model_id=mapped_model.model_id)
        export_controller.set_output_path(temp_path)
        samples_count = export_controller.run_export()

        # Should export only 2 samples (not 3)
        assert samples_count == 2

        # Check file content
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 2

    finally:
        temp_path.unlink(missing_ok=True)
