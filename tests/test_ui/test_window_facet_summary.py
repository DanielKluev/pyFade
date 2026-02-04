"""
UI tests for FacetSummaryWindow.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PyQt6.QtTest import QSignalSpy

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.gui.window_facet_summary import FacetSummaryWindow
from tests.helpers.data_helpers import create_test_sample_with_completion, create_test_completion_with_params, create_test_logprobs

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def wait_for_report(window: FacetSummaryWindow, qt_app: "QApplication", timeout: int = 5000) -> None:
    """
    Wait for the summary report to be generated.

    Args:
        window: The FacetSummaryWindow instance
        qt_app: QApplication instance
        timeout: Maximum time to wait in milliseconds
    """
    if window.report is not None:
        return

    # Wait for the worker thread to finish
    if window.worker_thread:
        spy = QSignalSpy(window.worker_thread.report_completed)
        spy.wait(timeout)
        qt_app.processEvents()


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
    window.show()  # Trigger showEvent which starts report generation
    wait_for_report(window, qt_app)

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
    window.show()
    wait_for_report(window, qt_app)
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
    window.show()
    wait_for_report(window, qt_app)
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
    # Add logprobs for rejected completion (required by DPO spec)
    create_test_logprobs(temp_dataset, completion2.id, mapped_model.model_id, min_logprob=-0.3, avg_logprob=-0.2)
    temp_dataset.commit()

    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    window.show()
    wait_for_report(window, qt_app)
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
    window.show()
    wait_for_report(window, qt_app)
    assert window.report is not None
    assert window.report.sft_total_samples == 1
    assert window.report.sft_finished_samples == 0
    assert window.report.sft_unfinished_samples == 1
    assert len(window.report.sft_unfinished_details) == 1
    assert "rating >= 7" in window.report.sft_unfinished_details[0].reasons[0]

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_displays_token_counts(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                    qt_app: "QApplication") -> None:
    """
    Test that the window displays completion token counts correctly.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7, min_logprob_threshold=-1.0,
                         avg_logprob_threshold=-0.4)
    temp_dataset.commit()

    mapped_model = app_with_dataset.providers_manager.get_mock_model()

    # Create a sample ready for SFT with known token count
    create_test_sample_with_completion(temp_dataset, facet, rating=8, min_logprob=-0.2, avg_logprob=-0.15)
    temp_dataset.commit()
    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)
    window.show()
    wait_for_report(window, qt_app)
    assert window.report is not None
    assert window.report.sft_total_samples == 1
    assert window.report.sft_finished_samples == 1
    assert window.report.sft_total_tokens > 0  # Should have counted tokens

    window.close()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_facet_summary_window_progress_elements(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                qt_app: "QApplication") -> None:
    """
    Test that the window has progress UI elements and they work correctly.
    """
    facet = Facet.create(temp_dataset, "Test Facet", "Test description")
    temp_dataset.commit()
    mapped_model = app_with_dataset.providers_manager.get_mock_model()
    window = FacetSummaryWindow(app_with_dataset, temp_dataset, facet, mapped_model)

    # Verify progress widgets exist
    assert window.progress_widget is not None
    assert window.progress_bar is not None
    assert window.progress_label is not None
    assert window.scroll_area is not None
    assert window.close_button is not None

    # Before showing, progress widget should be visible and scroll area hidden
    window.show()

    # Initially, close button should be disabled
    assert window.close_button.isEnabled() is False

    # Wait for completion
    wait_for_report(window, qt_app)

    # After completion, close button should be enabled
    assert window.close_button.isEnabled() is True

    # Progress widget should be hidden and scroll area visible
    assert window.progress_widget.isVisible() is False
    assert window.scroll_area.isVisible() is True

    window.close()
