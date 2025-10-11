"""
UI tests for FacetSummaryWindow.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.gui.window_facet_summary import FacetSummaryWindow
from tests.conftest import app_with_dataset
from tests.helpers.data_helpers import create_test_sample_with_completion, create_test_completion_with_params

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_initialization(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                             qt_app: "QApplication") -> None:
    """
    Test that the facet summary window initializes correctly.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()
    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    qt_app.processEvents()

    assert window.windowTitle() == "Facet Summary: Test Facet"
    assert window.report is not None
    assert window.report.facet_name == "Test Facet"
    assert window.report.target_model_id == mapped_model.model_id

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_empty_facet(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                   qt_app: "QApplication") -> None:
    """
    Test that the window displays correctly for an empty facet.
    """
    facet = Facet.create(temp_dataset, "Empty Facet", "No samples")
    temp_dataset.commit()
    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    qt_app.processEvents()
    assert window.report is not None
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

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create a sample ready for SFT
    create_test_sample_with_completion(temp_dataset, facet, rating=8, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()
    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    qt_app.processEvents()
    assert window.report is not None
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
    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create sample with good completion and a lower-rated one
    sample1, _ = create_test_sample_with_completion(temp_dataset, facet, rating=9, min_logprob=-0.2, avg_logprob=-0.15)

    # Add another completion with lower rating to the same sample
    completion2 = create_test_completion_with_params(temp_dataset, sample1.prompt_revision, sha256="b" * 64,
                                                     completion_text="Bad completion")
    PromptCompletionRating.set_rating(temp_dataset, completion2, facet, 4)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    qt_app.processEvents()
    assert window.report is not None
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
    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    # Create a sample with low rating (unfinished)
    create_test_sample_with_completion(temp_dataset, facet, rating=5, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    qt_app.processEvents()
    assert window.report is not None
    assert window.report.sft_total_samples == 1
    assert window.report.sft_finished_samples == 0
    assert window.report.sft_unfinished_samples == 1
    assert len(window.report.sft_unfinished_details) == 1
    assert "rating >= 7" in window.report.sft_unfinished_details[0].reasons[0]

    window.close()
