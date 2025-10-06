"""
UI tests for FacetSummaryWindow.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from py_fade.data_formats.base_data_classes import CompletionTopLogprobs
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.window_facet_summary import FacetSummaryWindow
from tests.helpers.data_helpers import create_test_single_position_token

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def create_test_sample_with_completion(temp_dataset, facet, rating: int, min_logprob: float, avg_logprob: float):
    """
    Helper to create a sample with a rated completion and logprobs for testing.
    """
    # Create sample and prompt
    sample = Sample(title="Test Sample", notes="Test sample", date_created=datetime.datetime.now())
    temp_dataset.session.add(sample)
    prompt = PromptRevision.new_from_text("Test prompt", context_length=2048, max_tokens=100)
    temp_dataset.session.add(prompt)
    sample.prompt_revision = prompt
    temp_dataset.session.flush()

    # Create completion
    completion = PromptCompletion(
        prompt_revision_id=prompt.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion)
    temp_dataset.session.flush()

    # Add rating
    PromptCompletionRating.set_rating(temp_dataset, completion, facet, rating)

    # Add logprobs
    sampled_logprobs_list = [
        create_test_single_position_token("Test", min_logprob).to_dict(),
        create_test_single_position_token(" completion", avg_logprob).to_dict()
    ]
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())

    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
    logprobs = PromptCompletionLogprobs(
        prompt_completion_id=completion.id,
        logprobs_model_id="test-model",
        sampled_logprobs=None,
        sampled_logprobs_json=sampled_logprobs_list,
        alternative_logprobs=None,
        alternative_logprobs_bin=alternative_logprobs_bin,
        min_logprob=min_logprob,
        avg_logprob=avg_logprob,
    )
    # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
    temp_dataset.session.add(logprobs)

    return sample, completion


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_initialization(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                             qt_app: "QApplication") -> None:
    """
    Test that the facet summary window initializes correctly.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, "test-model")
    qt_app.processEvents()

    assert window.windowTitle() == "Facet Summary: Test Facet"
    assert window.report is not None
    assert window.report.facet_name == "Test Facet"
    assert window.report.target_model_id == "test-model"

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_empty_facet(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                   qt_app: "QApplication") -> None:
    """
    Test that the window displays correctly for an empty facet.
    """
    facet = Facet.create(temp_dataset, "Empty Facet", "No samples")
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, "test-model")
    qt_app.processEvents()

    assert window.report.sft_total_samples == 0
    assert window.report.dpo_total_samples == 0

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_sft_ready_sample(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                        qt_app: "QApplication") -> None:
    """
    Test that the window correctly shows a sample ready for SFT.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create a sample ready for SFT
    create_test_sample_with_completion(temp_dataset, facet, rating=8, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, "test-model")
    qt_app.processEvents()

    assert window.report.sft_total_samples == 1
    assert window.report.sft_finished_samples == 1
    assert window.report.sft_unfinished_samples == 0

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_dpo_ready_sample(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                        qt_app: "QApplication") -> None:
    """
    Test that the window correctly shows a sample ready for DPO.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create sample with good completion and a lower-rated one
    sample1, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.2, avg_logprob=-0.15)

    # Add another completion with lower rating to the same sample
    completion2 = PromptCompletion(
        prompt_revision_id=sample1.prompt_revision.id,
        sha256="b" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Bad completion",
        context_length=2048,
        max_tokens=100,
    )
    temp_dataset.session.add(completion2)
    temp_dataset.session.flush()
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 4)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, "test-model")
    qt_app.processEvents()

    assert window.report.dpo_total_samples == 1
    assert window.report.dpo_finished_samples == 1
    assert window.report.dpo_unfinished_samples == 0

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_unfinished_samples(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                          qt_app: "QApplication") -> None:
    """
    Test that the window displays unfinished sample details.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    # Create a sample with low rating (unfinished)
    create_test_sample_with_completion(temp_dataset, facet, rating=5, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, "test-model")
    qt_app.processEvents()

    assert window.report.sft_total_samples == 1
    assert window.report.sft_finished_samples == 0
    assert window.report.sft_unfinished_samples == 1
    assert len(window.report.sft_unfinished_details) == 1
    assert "rating >= 7" in window.report.sft_unfinished_details[0].reasons[0]

    window.close()
