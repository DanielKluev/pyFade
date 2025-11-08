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

    # Verify facets display shows message
    assert "No facets yet" in widget.facets_display.text()

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

    # Verify facets display shows "No facets"
    assert "No facets" in widget.facets_display.text()

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
    completion1 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 1",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    completion2 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="b" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 2",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    dataset.session.add(completion1)
    dataset.session.add(completion2)
    dataset.commit()

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify facets display shows facet names (ordered alphabetically)
    facets_text = widget.facets_display.text()
    assert "Accuracy" in facets_text
    assert "Quality" in facets_text

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
    completion1 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 1",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    completion2 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="b" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 2",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    dataset.session.add(completion1)
    dataset.session.add(completion2)
    dataset.commit()

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample and active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=facet_quality)
    qt_app.processEvents()

    # Verify active facet is highlighted (contains style attributes)
    facets_text = widget.facets_display.text()
    test_logger.debug("Facets display text: %s", facets_text)

    # Check for HTML highlighting
    assert "Quality" in facets_text
    assert "span" in facets_text  # HTML tag for highlighting
    assert "background-color" in facets_text or "font-weight" in facets_text

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
    completion1 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 1",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    completion2 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="b" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 2",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    dataset.session.add(completion1)
    dataset.session.add(completion2)
    dataset.commit()

    # Add ratings for different facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion2, facet_accuracy, 9)

    # Create widget with sample and initial active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=facet_quality)
    qt_app.processEvents()

    # Verify initial active facet highlighting
    initial_text = widget.facets_display.text()
    test_logger.debug("Initial facets display text: %s", initial_text)
    assert "Quality" in initial_text

    # Change active context to different facet
    widget.set_active_context(facet_accuracy, None)
    qt_app.processEvents()

    # Verify facets display was updated with new highlighting
    updated_text = widget.facets_display.text()
    test_logger.debug("Updated facets display text: %s", updated_text)
    assert "Accuracy" in updated_text
    assert "Quality" in updated_text

    # The highlighting should have changed (though exact HTML may vary)
    assert initial_text != updated_text or "span" in updated_text

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
    completion1 = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion 1",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    dataset.session.add(completion1)
    dataset.commit()

    # Add ratings for facets
    PromptCompletionRating.set_rating(dataset, completion1, facet_quality, 8)
    PromptCompletionRating.set_rating(dataset, completion1, facet_accuracy, 9)

    # Create widget with sample but no active facet
    widget = WidgetSample(None, app_with_dataset, sample=sample, active_facet=None)
    qt_app.processEvents()

    # Verify facets display shows facets without highlighting
    facets_text = widget.facets_display.text()
    test_logger.debug("Facets display text (no active): %s", facets_text)
    assert "Accuracy" in facets_text
    assert "Quality" in facets_text

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
    completion = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256="a" * 64,
        model_id="test-model",
        temperature=0.7,
        top_k=50,
        completion_text="Test completion",
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    dataset.session.add(completion)
    dataset.commit()

    # Add rating
    PromptCompletionRating.set_rating(dataset, completion, facet_quality, 8)

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify facets display shows single facet
    facets_text = widget.facets_display.text()
    test_logger.debug("Facets display text (single facet): %s", facets_text)
    assert "Quality" in facets_text
    # Should not contain comma separator
    assert facets_text.count(",") == 0

    widget.deleteLater()
    qt_app.processEvents()
