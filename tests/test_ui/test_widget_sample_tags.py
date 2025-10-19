"""
Test suite for sample tags display and editing in WidgetSample.

Tests sample tags functionality including:
- Tags display in sample widget
- Edit tags button functionality
- Tags update after editing
- New sample tags handling
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_tag import SampleTag  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.tag import Tag
from py_fade.gui.widget_sample import WidgetSample
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp


def test_widget_sample_tags_display_new_sample(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that new samples show message to save first.

    Verifies that the tags display shows appropriate message for unsaved samples.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.new_sample")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create widget with new sample (None)
    widget = WidgetSample(None, app_with_dataset, sample=None)
    qt_app.processEvents()

    # Verify tags display shows message
    assert "Save sample first" in widget.tags_display.text()
    assert not widget.edit_tags_button.isEnabled()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_tags_display_no_tags(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples without tags show appropriate message.

    Verifies that the tags display shows "No tags" for samples without any tags.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.no_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a sample
    dataset = app_with_dataset.current_dataset
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)
    dataset.commit()

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify tags display shows "No tags"
    assert "No tags" in widget.tags_display.text()
    assert widget.edit_tags_button.isEnabled()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_tags_display_with_tags(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that samples with tags show tag names.

    Verifies that the tags display shows comma-separated tag names.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.with_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    dataset = app_with_dataset.current_dataset
    tag1 = Tag.create(dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(dataset, "Reviewed", "Reviewed samples", scope="both")
    dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)
    dataset.commit()

    # Add tags to sample
    sample.add_tag(dataset, tag1)
    sample.add_tag(dataset, tag2)
    dataset.commit()

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify tags display shows tag names
    tags_text = widget.tags_display.text()
    assert "Important" in tags_text
    assert "Reviewed" in tags_text

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_edit_tags_button_opens_dialog(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that clicking edit tags button opens the dialog.

    Verifies that the edit tags button triggers the dialog to open.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.edit_button")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a sample
    dataset = app_with_dataset.current_dataset
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)
    dataset.commit()

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Mock the dialog to avoid actually opening it
    with patch("py_fade.gui.dialog_sample_tags.SampleTagsDialog") as mock_dialog_class:
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 0  # DialogCode.Rejected
        mock_dialog_class.return_value = mock_dialog

        # Click edit tags button
        widget.edit_tags_button.click()
        qt_app.processEvents()

        # Verify dialog was created and shown
        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_edit_tags_updates_display(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that accepting the dialog updates the tags display.

    Verifies that tags display is refreshed after editing tags.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.update_display")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    dataset = app_with_dataset.current_dataset
    tag1 = Tag.create(dataset, "Important", "Important samples", scope="samples")
    dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_revision)
    dataset.commit()

    # Create widget with sample
    widget = WidgetSample(None, app_with_dataset, sample=sample)
    qt_app.processEvents()

    # Verify initial state (no tags)
    assert "No tags" in widget.tags_display.text()

    # Mock the dialog to simulate adding a tag
    with patch("py_fade.gui.dialog_sample_tags.SampleTagsDialog") as mock_dialog_class:
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # DialogCode.Accepted

        # Simulate adding tag through dialog
        def add_tag_side_effect(*args, **kwargs):
            sample.add_tag(dataset, tag1)
            dataset.commit()
            return 1

        mock_dialog.exec.side_effect = add_tag_side_effect
        mock_dialog_class.return_value = mock_dialog

        # Click edit tags button
        widget.edit_tags_button.click()
        qt_app.processEvents()

    # Verify tags display was updated
    assert "Important" in widget.tags_display.text()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_edit_tags_new_sample_shows_warning(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that trying to edit tags on new sample shows warning.

    Edge case: attempting to edit tags on unsaved sample should show warning.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_tags.new_sample_warning")
    test_logger.setLevel(logging.DEBUG)

    warning_shown = []

    def mock_warning(parent, title, message):
        warning_shown.append((title, message))
        test_logger.debug("Warning shown: %s - %s", title, message)

    monkeypatch.setattr("py_fade.gui.widget_sample.QMessageBox.warning", mock_warning)

    # Create widget with new sample (None)
    widget = WidgetSample(None, app_with_dataset, sample=None)
    qt_app.processEvents()

    # Simulate saving the sample (which should create a sample with ID)
    widget.prompt_area.setPlainText("Test prompt")
    widget.title_field.setText("Test Sample")
    widget.save_sample()
    qt_app.processEvents()

    # Now widget.sample should be set
    # But let's test the case where sample doesn't have ID yet
    widget.sample = Sample(
        title="Unsaved Sample",
        group_path=None,
        notes=None,
        prompt_revision=None,
    )
    widget.update_tags_display()
    qt_app.processEvents()

    # Try to edit tags
    widget.edit_tags()
    qt_app.processEvents()

    # Verify warning was shown
    assert len(warning_shown) > 0
    assert "save" in warning_shown[0][1].lower()

    widget.deleteLater()
    qt_app.processEvents()
