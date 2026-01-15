"""
Test suite for sample facets display in WidgetSample.

Tests facets display functionality including:
- Facets display in sample widget right panel
- Highlighting of active facet
- Facets update when changing active context
- New sample facets handling
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.widget_sample import WidgetSample
from tests.helpers.data_helpers import create_test_completion_pair
from tests.helpers.ui_helpers import create_test_widget_sample_with_prompt, patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp


def test_widget_sample_facets_display_new_sample(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that new samples show message for facets.

    Verifies that the facets display shows appropriate message for unsaved samples.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.new_sample")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create widget with new sample (None)
    widget = WidgetSample(None, app_with_dataset, sample=None)
    qt_app.processEvents()

    # Verify facets display shows message (check placeholder text)
    assert "No facets yet" in widget.facets_display.placeholder_label.text()
    # Verify no facet labels are shown
    assert len(widget.facets_display.facet_labels) == 0

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_no_facets(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples without facets show appropriate message.

    Verifies that the facets display shows "No facets" for samples without any ratings.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.no_facets")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a sample without ratings
    widget, _sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)

    # Verify facets display shows "No facets" (check placeholder)
    assert "No facets" in widget.facets_display.placeholder_label.text()
    # Verify no facet labels are shown
    assert len(widget.facets_display.facet_labels) == 0

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_with_facets(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples with facets show facet names.

    Verifies that the facets display shows comma-separated facet names.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.with_facets")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    dataset = app_with_dataset.current_dataset
    facet_quality = Facet.create(dataset, "Quality", "Quality facet")
    facet_accuracy = Facet.create(dataset, "Accuracy", "Accuracy facet")
    dataset.commit()

    # Create sample with rated completions
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)

    # Add completions with ratings for different facets
    completion1, completion2 = create_test_completion_pair(dataset, prompt_revision)

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify facets display shows facet names
    # Check that both facets are in the widget
    facet_names = [label.text() for label in widget.facets_display.facet_labels if hasattr(label, 'facet')]
    assert "Accuracy" in facet_names
    assert "Quality" in facet_names
    assert len([label for label in widget.facets_display.facet_labels if hasattr(label, 'facet')]) == 2

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_highlight_active(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that active facet is highlighted in the display.

    Verifies that when an active facet is set, it's displayed with highlighting.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.highlight_active")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    dataset = app_with_dataset.current_dataset
    facet_quality = Facet.create(dataset, "Quality", "Quality facet")
    facet_accuracy = Facet.create(dataset, "Accuracy", "Accuracy facet")
    dataset.commit()

    # Create sample with rated completions
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)

    # Add completions with ratings for different facets
    completion1, completion2 = create_test_completion_pair(dataset, prompt_revision)

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample and active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=facet_quality)
    qt_app.processEvents()

    # Verify active facet is highlighted (check for active styling)
    # Find the Quality facet label
    quality_label = None
    for label in widget.facets_display.facet_labels:
        if hasattr(label, 'facet') and label.facet.name == "Quality":
            quality_label = label
            break

    assert quality_label is not None
    # Check that Quality facet has active styling (green background)
    assert "#4CAF50" in quality_label.styleSheet()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_update_on_context_change(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that facets display updates when active context changes.

    Verifies that changing the active facet updates the highlighting in the display.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.context_change")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    dataset = app_with_dataset.current_dataset
    facet_quality = Facet.create(dataset, "Quality", "Quality facet")
    facet_accuracy = Facet.create(dataset, "Accuracy", "Accuracy facet")
    dataset.commit()

    # Create sample with rated completions
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)

    # Add completions with ratings for different facets
    completion1, completion2 = create_test_completion_pair(dataset, prompt_revision)

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample and initial active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=facet_quality)
    qt_app.processEvents()

    # Verify initial active facet highlighting
    # Find Quality facet
    quality_label_before = None
    for label in widget.facets_display.facet_labels:
        if hasattr(label, 'facet') and label.facet.name == "Quality":
            quality_label_before = label
            break
    assert quality_label_before is not None
    test_logger.debug("Initial Quality label style: %s", quality_label_before.styleSheet())

    # Change active context to different facet
    widget.set_active_context(facet_accuracy, None)
    qt_app.processEvents()

    # Verify facets display was updated with new highlighting
    # Find Accuracy facet
    accuracy_label_after = None
    for label in widget.facets_display.facet_labels:
        if hasattr(label, 'facet') and label.facet.name == "Accuracy":
            accuracy_label_after = label
            break
    assert accuracy_label_after is not None
    test_logger.debug("Updated Accuracy label style: %s", accuracy_label_after.styleSheet())

    # Verify Accuracy is now highlighted
    assert "#4CAF50" in accuracy_label_after.styleSheet()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_no_active_facet(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that facets display works correctly with no active facet.

    Verifies that when no active facet is set, all facets are shown without highlighting.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.no_active")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facets
    dataset = app_with_dataset.current_dataset
    facet_quality = Facet.create(dataset, "Quality", "Quality facet")
    facet_accuracy = Facet.create(dataset, "Accuracy", "Accuracy facet")
    dataset.commit()

    # Create sample with rated completions
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)

    # Add completions with ratings for different facets
    completion, _ = create_test_completion_pair(dataset, prompt_revision)

    # Add ratings for facets
    PromptCompletionRating.set_rating(dataset, completion, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion, facet_accuracy, 9)

    # Create widget with sample but no active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=None)
    qt_app.processEvents()

    # Verify facets display shows facets without highlighting
    facet_names = [label.text() for label in widget.facets_display.facet_labels if hasattr(label, 'facet')]
    test_logger.debug("Facets display (no active): %s", facet_names)
    assert "Accuracy" in facet_names
    assert "Quality" in facet_names
    # Verify none are highlighted with active color
    for label in widget.facets_display.facet_labels:
        if hasattr(label, 'facet'):
            assert "#4CAF50" not in label.styleSheet()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_facets_display_single_facet(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that facets display works correctly with a single facet.

    Verifies display when sample has ratings for only one facet.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_facets.single_facet")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create facet
    dataset = app_with_dataset.current_dataset
    facet_quality = Facet.create(dataset, "Quality", "Quality facet")
    dataset.commit()

    # Create sample with rated completion
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)

    # Add completion with rating
    completion, _ = create_test_completion_pair(dataset, prompt_revision, completion_text_1="Test completion")

    # Add rating
    PromptCompletionRating.set_rating(dataset, completion, facet_quality, 8)

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify facets display shows single facet
    facet_names = [label.text() for label in widget.facets_display.facet_labels if hasattr(label, 'facet')]
    test_logger.debug("Facets display (single facet): %s", facet_names)
    assert "Quality" in facet_names
    # Should be exactly one facet label (no separators count as facets)
    assert len(facet_names) == 1

    widget.deleteLater()
    qt_app.processEvents()
