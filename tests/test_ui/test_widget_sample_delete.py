"""
Test suite for sample deletion functionality in WidgetSample.

Tests delete sample feature including:
- Delete button exists and is visible
- Confirmation dialog appears before deletion
- Successful deletion of saved samples
- Cancellation of deletion
- Deletion of partially saved samples (prompt+completion without sample)
- UI state after deletion
- Signal emission on deletion
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import QMessageBox

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.providers.llm_response import LLMResponse
from tests.helpers.ui_helpers import create_test_widget_sample_with_prompt, create_test_widget_sample_empty, patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp


def test_delete_button_exists(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that the delete button exists in the sample widget.

    Verifies that the delete button is created and visible in the UI.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.button_exists")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a widget with a sample
    widget, _sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)

    # Verify delete button exists
    assert hasattr(widget, "delete_button"), "Delete button should exist"
    assert widget.delete_button is not None, "Delete button should not be None"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_saved_sample_with_confirmation(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test successful deletion of a saved sample with confirmation.

    Verifies that:
    - Confirmation dialog is shown
    - Sample is deleted from database
    - PromptRevision is also deleted from database
    - Signal is emitted after deletion
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.saved_sample")
    test_logger.setLevel(logging.DEBUG)

    # Track signal emission
    signal_emitted = {"called": False, "sample": None}

    def signal_handler(sample):
        signal_emitted["called"] = True
        signal_emitted["sample"] = sample

    # Create a widget with a sample
    widget, sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)
    sample_id = sample.id
    prompt_revision_id = sample.prompt_revision.id
    dataset = app_with_dataset.current_dataset

    # Connect signal
    widget.sample_deleted.connect(signal_handler)

    # Mock QMessageBox to auto-confirm deletion
    def mock_question(*args, **kwargs):
        test_logger.debug("QMessageBox.question called with args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Yes

    def mock_information(*args, **kwargs):
        test_logger.debug("QMessageBox.information called with args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "question", staticmethod(mock_question))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(mock_information))

    # Trigger deletion
    widget.delete_sample()
    qt_app.processEvents()

    # Verify sample was deleted from database
    deleted_sample = dataset.session.query(Sample).filter_by(id=sample_id).first()
    assert deleted_sample is None, "Sample should be deleted from database"

    # Verify prompt_revision was also deleted
    deleted_prompt = dataset.session.query(PromptRevision).filter_by(id=prompt_revision_id).first()
    assert deleted_prompt is None, "PromptRevision should be deleted from database"

    # Verify signal was emitted
    assert signal_emitted["called"], "sample_deleted signal should be emitted"
    assert signal_emitted["sample"] is not None, "Deleted sample should be passed to signal"

    # Verify widget state is cleared
    assert widget.sample is None, "Widget sample should be None after deletion"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_sample_cancellation(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test cancellation of sample deletion.

    Verifies that:
    - Sample is NOT deleted when user cancels
    - Signal is NOT emitted
    - Sample remains in database
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.cancellation")
    test_logger.setLevel(logging.DEBUG)

    # Track signal emission
    signal_emitted = {"called": False}

    def signal_handler(_sample):
        signal_emitted["called"] = True

    # Create a widget with a sample
    widget, sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)
    sample_id = sample.id
    dataset = app_with_dataset.current_dataset

    # Connect signal
    widget.sample_deleted.connect(signal_handler)

    # Mock QMessageBox to cancel deletion
    def mock_question(*args, **kwargs):
        test_logger.debug("QMessageBox.question called - returning No")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(mock_question))

    # Trigger deletion (should be cancelled)
    widget.delete_sample()
    qt_app.processEvents()

    # Verify sample still exists in database
    existing_sample = dataset.session.query(Sample).filter_by(id=sample_id).first()
    assert existing_sample is not None, "Sample should still exist in database after cancellation"

    # Verify signal was NOT emitted
    assert not signal_emitted["called"], "sample_deleted signal should NOT be emitted on cancellation"

    # Verify widget state is unchanged
    assert widget.sample is not None, "Widget sample should still exist after cancellation"
    assert widget.sample.id == sample_id, "Widget sample ID should be unchanged"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_partially_saved_sample(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test deletion of partially saved sample (prompt+completion exist, but no sample).

    Verifies that:
    - Confirmation dialog is shown
    - Prompt revision and completions are deleted
    - Signal is emitted (with None sample)
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.partial_sample")
    test_logger.setLevel(logging.DEBUG)

    # Track signal emission
    signal_emitted = {"called": False, "sample": "not_set"}

    def signal_handler(sample):
        signal_emitted["called"] = True
        signal_emitted["sample"] = sample

    # Create a widget without a saved sample, but with prompt and completion
    widget = create_test_widget_sample_empty(app_with_dataset, qt_app)
    dataset = app_with_dataset.current_dataset

    # Set a prompt
    widget.prompt_area.setPlainText("Test prompt for partial sample")

    # Create a completion using the widget's add_completion method
    mock_response = LLMResponse(
        model_id="mock-echo-model",
        prompt_conversation=[],
        completion_text="Test completion",
        generated_part_text="Test completion",
        temperature=0.7,
        top_k=40,
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    widget.add_completion(mock_response)
    prompt_revision_id = widget.last_prompt_revision.id
    qt_app.processEvents()

    # Connect signal
    widget.sample_deleted.connect(signal_handler)

    # Mock QMessageBox to auto-confirm deletion
    def mock_question(*args, **kwargs):
        test_logger.debug("QMessageBox.question called with args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Yes

    def mock_information(*args, **kwargs):
        test_logger.debug("QMessageBox.information called with args=%s kwargs=%s", args, kwargs)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "question", staticmethod(mock_question))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(mock_information))

    # Trigger deletion
    widget.delete_sample()
    qt_app.processEvents()

    # Verify prompt_revision was deleted from database
    deleted_prompt = dataset.session.query(PromptRevision).filter_by(id=prompt_revision_id).first()
    assert deleted_prompt is None, "PromptRevision should be deleted from database"

    # Verify signal was emitted with None (no saved sample)
    assert signal_emitted["called"], "sample_deleted signal should be emitted"
    assert signal_emitted["sample"] is None, "Signal should pass None for partially saved sample"

    # Verify widget state is cleared
    assert widget.sample is None, "Widget sample should be None after deletion"
    assert widget.last_prompt_revision is None, "Widget last_prompt_revision should be None after deletion"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_sample_with_tags_and_images(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test deletion of sample with associated tags and images.

    Verifies that:
    - Sample with tags is deleted
    - Associated SampleTag entries are deleted (cascade)
    - Associated SampleImage entries are deleted (cascade)
    - PromptRevision is also deleted
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.with_associations")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    from py_fade.dataset.tag import Tag  # pylint: disable=import-outside-toplevel
    from py_fade.dataset.sample_tag import SampleTag  # pylint: disable=import-outside-toplevel

    # Create a widget with a sample
    widget, sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)
    dataset = app_with_dataset.current_dataset
    sample_id = sample.id
    prompt_revision_id = sample.prompt_revision.id

    # Add a tag to the sample
    tag = Tag.create(dataset, "Test Tag", "Test tag description")
    dataset.session.commit()
    sample.add_tag(dataset, tag)
    dataset.session.commit()

    # Verify tag association exists
    tag_association = dataset.session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag.id).first()
    assert tag_association is not None, "SampleTag association should exist before deletion"

    # Trigger deletion
    widget.delete_sample()
    qt_app.processEvents()

    # Verify sample was deleted
    deleted_sample = dataset.session.query(Sample).filter_by(id=sample_id).first()
    assert deleted_sample is None, "Sample should be deleted from database"

    # Verify prompt_revision was also deleted
    deleted_prompt = dataset.session.query(PromptRevision).filter_by(id=prompt_revision_id).first()
    assert deleted_prompt is None, "PromptRevision should be deleted from database"

    # Verify tag association was deleted (cascade)
    deleted_association = dataset.session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag.id).first()
    assert deleted_association is None, "SampleTag association should be deleted with sample"

    # Tag itself should still exist
    existing_tag = dataset.session.query(Tag).filter_by(id=tag.id).first()
    assert existing_tag is not None, "Tag should still exist after sample deletion"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_empty_sample_shows_warning(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that deleting an empty sample (no sample, no prompt) shows warning.

    Verifies that:
    - Warning message is shown
    - No deletion occurs
    - No signal is emitted
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.empty_sample")
    test_logger.setLevel(logging.DEBUG)

    # Track signal emission
    signal_emitted = {"called": False}

    def signal_handler(_sample):
        signal_emitted["called"] = True

    # Track warning dialog
    warning_shown = {"called": False}

    def mock_warning(*args, **kwargs):
        test_logger.debug("QMessageBox.warning called with args=%s kwargs=%s", args, kwargs)
        warning_shown["called"] = True
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(mock_warning))

    # Create an empty widget
    widget = create_test_widget_sample_empty(app_with_dataset, qt_app)

    # Connect signal
    widget.sample_deleted.connect(signal_handler)

    # Trigger deletion on empty widget
    widget.delete_sample()
    qt_app.processEvents()

    # Verify warning was shown
    assert warning_shown["called"], "Warning dialog should be shown for empty sample"

    # Verify signal was NOT emitted
    assert not signal_emitted["called"], "sample_deleted signal should NOT be emitted for empty sample"

    widget.deleteLater()
    qt_app.processEvents()


def test_delete_sample_database_error_handling(
    app_with_dataset: "pyFadeApp",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test error handling when database deletion fails.

    Verifies that:
    - Error dialog is shown
    - Transaction is rolled back
    - Sample still exists in database
    - Signal is NOT emitted
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSample")
    test_logger = logging.getLogger("test_widget_sample_delete.error_handling")
    test_logger.setLevel(logging.DEBUG)

    # Track signal emission
    signal_emitted = {"called": False}

    def signal_handler(_sample):
        signal_emitted["called"] = True

    # Track error dialog
    error_shown = {"called": False}

    def mock_critical(*args, **kwargs):
        test_logger.debug("QMessageBox.critical called with args=%s kwargs=%s", args, kwargs)
        error_shown["called"] = True
        return QMessageBox.StandardButton.Ok

    def mock_question(*args, **kwargs):
        test_logger.debug("QMessageBox.question called - returning Yes")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(mock_question))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(mock_critical))

    # Create a widget with a sample
    widget, sample = create_test_widget_sample_with_prompt(app_with_dataset, qt_app)
    sample_id = sample.id
    dataset = app_with_dataset.current_dataset

    # Connect signal
    widget.sample_deleted.connect(signal_handler)

    # Mock the delete method to raise an exception
    def failing_delete(_dataset):
        raise RuntimeError("Simulated database error")

    monkeypatch.setattr(sample, "delete", failing_delete)

    # Trigger deletion (should fail)
    widget.delete_sample()
    qt_app.processEvents()

    # Verify error dialog was shown
    assert error_shown["called"], "Error dialog should be shown on database error"

    # Verify sample still exists in database
    existing_sample = dataset.session.query(Sample).filter_by(id=sample_id).first()
    assert existing_sample is not None, "Sample should still exist after failed deletion"

    # Verify signal was NOT emitted
    assert not signal_emitted["called"], "sample_deleted signal should NOT be emitted on error"

    widget.deleteLater()
    qt_app.processEvents()
