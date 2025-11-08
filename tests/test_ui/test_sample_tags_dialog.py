"""
Test suite for SampleTagsDialog UI component.

Tests tag selection dialog functionality including:
- Dialog initialization and display
- Tag checkbox creation and state
- Adding tags to samples
- Removing tags from samples
- Multiple tag management
- Tag count updates
- Sample without tags display
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import QCheckBox

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_tag import SampleTag  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.tag import Tag
from py_fade.gui.dialog_sample_tags import SampleTagsDialog
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase


def test_sample_tags_dialog_initialization(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test initializing the sample tags dialog.

    Verifies that the dialog is properly initialized with sample information.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.initialization")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Verify dialog properties
    assert dialog.sample == sample
    assert dialog.dataset == temp_dataset
    assert "Test Sample" in dialog.windowTitle()

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_displays_no_tags_message(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that dialog displays message when no tags are available.

    Edge case: when no tags exist in the dataset, show appropriate message.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.no_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog (no tags exist yet)
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Verify no checkboxes were created
    assert len(dialog.tag_checkboxes) == 0

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_displays_available_tags(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that dialog displays all available tags with appropriate scope.

    Verifies that tags with scope 'samples' or 'both' are displayed.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.display_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags with different scopes
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples", scope="both")
    tag3 = Tag.create(temp_dataset, "Completion Tag", "For completions only", scope="completions")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Verify only tags with scope 'samples' or 'both' are displayed
    assert len(dialog.tag_checkboxes) == 2  # tag1 and tag2, not tag3
    assert tag1.id in dialog.tag_checkboxes
    assert tag2.id in dialog.tag_checkboxes
    assert tag3.id not in dialog.tag_checkboxes

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_shows_existing_tags_checked(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that dialog shows existing tags as checked.

    Verifies that tags already associated with the sample are pre-checked.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.existing_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples", scope="both")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Add tag1 to sample
    sample.add_tag(temp_dataset, tag1)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Verify tag1 is checked, tag2 is not
    assert dialog.tag_checkboxes[tag1.id].isChecked()
    assert not dialog.tag_checkboxes[tag2.id].isChecked()

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_add_tag(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test adding a tag to a sample through the dialog.

    Verifies that checking a tag checkbox and accepting adds the tag to the sample.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.add_tag")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Check the tag checkbox
    dialog.tag_checkboxes[tag1.id].setChecked(True)
    qt_app.processEvents()

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify tag was added
    assert sample.has_tag(temp_dataset, tag1)

    # Verify tag count was updated
    tag1_refreshed = Tag.get_by_id(temp_dataset, tag1.id)
    assert tag1_refreshed is not None
    assert tag1_refreshed.total_samples == 1

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_remove_tag(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test removing a tag from a sample through the dialog.

    Verifies that unchecking a tag checkbox and accepting removes the tag from the sample.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.remove_tag")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Add tag to sample
    sample.add_tag(temp_dataset, tag1)
    tag1.update_sample_count(temp_dataset)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Verify tag is checked
    assert dialog.tag_checkboxes[tag1.id].isChecked()

    # Uncheck the tag checkbox
    dialog.tag_checkboxes[tag1.id].setChecked(False)
    qt_app.processEvents()

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify tag was removed
    assert not sample.has_tag(temp_dataset, tag1)

    # Verify tag count was updated
    tag1_refreshed = Tag.get_by_id(temp_dataset, tag1.id)
    assert tag1_refreshed is not None
    assert tag1_refreshed.total_samples == 0

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_multiple_tags(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test managing multiple tags through the dialog.

    Verifies that multiple tags can be added and removed in a single dialog session.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.multiple_tags")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples", scope="both")
    tag3 = Tag.create(temp_dataset, "Complete", "Complete samples", scope="samples")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Add tag1 to sample initially
    sample.add_tag(temp_dataset, tag1)
    tag1.update_sample_count(temp_dataset)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Remove tag1, add tag2 and tag3
    dialog.tag_checkboxes[tag1.id].setChecked(False)
    dialog.tag_checkboxes[tag2.id].setChecked(True)
    dialog.tag_checkboxes[tag3.id].setChecked(True)
    qt_app.processEvents()

    # Accept dialog
    dialog.accept()
    qt_app.processEvents()

    # Verify changes
    assert not sample.has_tag(temp_dataset, tag1)
    assert sample.has_tag(temp_dataset, tag2)
    assert sample.has_tag(temp_dataset, tag3)

    # Verify tag counts
    tag1_refreshed = Tag.get_by_id(temp_dataset, tag1.id)
    tag2_refreshed = Tag.get_by_id(temp_dataset, tag2.id)
    tag3_refreshed = Tag.get_by_id(temp_dataset, tag3.id)
    assert tag1_refreshed is not None and tag1_refreshed.total_samples == 0
    assert tag2_refreshed is not None and tag2_refreshed.total_samples == 1
    assert tag3_refreshed is not None and tag3_refreshed.total_samples == 1

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_cancel_does_not_save(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that canceling the dialog does not save changes.

    Verifies that changes made to checkboxes are not committed if dialog is rejected.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.cancel")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples", scope="samples")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Check the tag checkbox
    dialog.tag_checkboxes[tag1.id].setChecked(True)
    qt_app.processEvents()

    # Reject dialog (cancel)
    dialog.reject()
    qt_app.processEvents()

    # Verify tag was NOT added
    assert not sample.has_tag(temp_dataset, tag1)

    dialog.deleteLater()
    qt_app.processEvents()


def test_sample_tags_dialog_sorts_tags_alphabetically(
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that tags are displayed in alphabetical order by name.

    Verifies that tags are sorted alphabetically (case-insensitive) regardless of creation order.
    """
    caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
    test_logger = logging.getLogger("test_sample_tags_dialog.tag_sorting")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create tags in non-alphabetical order (intentionally unused, created for side effect)
    _tag_zebra = Tag.create(temp_dataset, "Zebra", "Last alphabetically", scope="samples")
    _tag_alpha = Tag.create(temp_dataset, "Alpha", "First alphabetically", scope="samples")
    _tag_middle = Tag.create(temp_dataset, "Middle", "Middle alphabetically", scope="both")
    _tag_beta = Tag.create(temp_dataset, "Beta", "Second alphabetically", scope="samples")
    temp_dataset.commit()

    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create dialog
    dialog = SampleTagsDialog(temp_dataset, sample)
    qt_app.processEvents()

    # Get the order of checkboxes by their position in the layout
    checkbox_labels = []
    for i in range(dialog.tags_layout.count()):
        widget = dialog.tags_layout.itemAt(i).widget()
        if isinstance(widget, QCheckBox):
            checkbox_labels.append(widget.text())

    # Verify tags are sorted alphabetically (case-insensitive)
    expected_order = ["Alpha", "Beta", "Middle", "Zebra"]
    assert checkbox_labels == expected_order, f"Expected {expected_order}, got {checkbox_labels}"

    dialog.deleteLater()
    qt_app.processEvents()
