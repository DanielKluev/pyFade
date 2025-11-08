"""
Test Widget Sample Notes Field.

Tests for the notes field UI in WidgetSample ensuring proper
display, editing, and persistence through the widget interface.
"""
import logging
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import QPlainTextEdit

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.widget_sample import WidgetSample
from tests.helpers.ui_helpers import create_test_widget_sample_empty

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class TestWidgetSampleNotes:
    """Test notes field functionality in WidgetSample."""

    def test_notes_field_exists(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes field exists in WidgetSample UI.

        Verifies that the notes field widget is created and accessible.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert hasattr(widget, "notes_field"), "Widget should have notes_field attribute"
        assert isinstance(widget.notes_field, QPlainTextEdit), "notes_field should be QPlainTextEdit"
        assert widget.notes_field is not None

    def test_notes_field_placeholder(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes field has appropriate placeholder text.

        Verifies that the placeholder guides users on the purpose of notes.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        placeholder = widget.notes_field.placeholderText()
        assert placeholder, "Notes field should have placeholder text"
        assert "notes" in placeholder.lower() or "annotator" in placeholder.lower(), \
            "Placeholder should mention notes or annotators"

    def test_notes_field_height_constraint(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                           ensure_google_icon_font: None) -> None:
        """
        Test that notes field has appropriate height constraint (about 2 lines).

        Verifies that the notes field doesn't take too much vertical space.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Maximum height should be set to keep it compact (around 60 pixels for 2 lines)
        max_height = widget.notes_field.maximumHeight()
        assert max_height <= 100, f"Notes field max height should be compact, got {max_height}"

    def test_new_sample_notes_empty(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes field is empty for new samples.

        Verifies initial state of notes field when no sample is loaded.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == "", "Notes field should be empty for new sample"

    def test_existing_sample_notes_populated(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                             ensure_google_icon_font: None) -> None:
        """
        Test that notes field is populated with existing sample's notes.

        Verifies that notes are loaded when opening an existing sample.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create a sample with notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt with notes", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample",
            prompt_revision=prompt_revision,
            notes="Important notes for this sample.",
        )

        assert sample is not None

        # Create widget with the sample
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == "Important notes for this sample."

    def test_existing_sample_without_notes(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                           ensure_google_icon_font: None) -> None:
        """
        Test that notes field is empty for samples without notes.

        Verifies backward compatibility with samples that don't have notes.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create a sample without notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt without notes", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(temp_dataset, title="Test Sample", prompt_revision=prompt_revision)

        assert sample is not None

        # Create widget with the sample
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == ""

    def test_save_new_sample_with_notes(
            self,
            qt_app: "QApplication",
            app_with_dataset: "pyFadeApp",
            temp_dataset: "DatasetDatabase",  # pylint: disable=unused-argument
            ensure_google_icon_font: None,
            caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that new sample can be saved with notes.

        Verifies that notes are persisted when creating a new sample.
        """
        caplog.set_level(logging.DEBUG, logger="WidgetSample")
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = create_test_widget_sample_empty(app_with_dataset, qt_app)

        # Fill in sample data
        widget.prompt_area.setPlainText("Test prompt for new sample")
        widget.title_field.setText("New Sample with Notes")
        widget.notes_field.setPlainText("These are notes for the new sample.")
        qt_app.processEvents()

        # Save the sample
        widget.save_sample()
        qt_app.processEvents()

        # Verify sample was created with notes
        assert widget.sample is not None
        assert widget.sample.notes == "These are notes for the new sample."
        assert widget.sample.title == "New Sample with Notes"

    def test_save_existing_sample_updates_notes(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Test that existing sample notes can be updated.

        Verifies that notes changes are persisted when saving existing sample.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create a sample with initial notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt for update", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample",
            prompt_revision=prompt_revision,
            notes="Initial notes.",
        )

        assert sample is not None
        sample_id = sample.id

        # Create widget and modify notes
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        widget.notes_field.setPlainText("Updated notes for this sample.")
        qt_app.processEvents()

        # Save the changes
        widget.save_sample()
        qt_app.processEvents()

        # Reload and verify update
        temp_dataset.session.expire_all()
        reloaded_sample = temp_dataset.session.query(Sample).filter_by(id=sample_id).first()
        assert reloaded_sample is not None
        assert reloaded_sample.notes == "Updated notes for this sample."

    def test_save_sample_empty_notes_converts_to_none(
            self,
            qt_app: "QApplication",
            app_with_dataset: "pyFadeApp",
            temp_dataset: "DatasetDatabase",  # pylint: disable=unused-argument
            ensure_google_icon_font: None) -> None:
        """
        Test that empty notes string is converted to None when saving.

        Verifies that empty notes are stored as NULL in database.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = create_test_widget_sample_empty(app_with_dataset, qt_app)

        # Fill in sample data with empty notes
        widget.prompt_area.setPlainText("Test prompt")
        widget.title_field.setText("Sample with Empty Notes")
        widget.notes_field.setPlainText("")
        qt_app.processEvents()

        # Save the sample
        widget.save_sample()
        qt_app.processEvents()

        # Verify sample was created with notes as None
        assert widget.sample is not None
        assert widget.sample.notes is None

    def test_notes_field_multiline_support(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                           ensure_google_icon_font: None) -> None:
        """
        Test that notes field supports multiline text.

        Verifies that notes with newlines are properly handled.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        multiline_notes = "Line 1: Important note\nLine 2: Another note\nLine 3: Final note"

        # Create a sample with multiline notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt multiline", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample",
            prompt_revision=prompt_revision,
            notes=multiline_notes,
        )

        assert sample is not None

        # Create widget and verify multiline display
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        displayed_notes = widget.notes_field.toPlainText()
        assert "\n" in displayed_notes
        assert displayed_notes == multiline_notes

    def test_notes_field_editable(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes field is editable by user.

        Verifies that users can type and modify notes.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Check field is not read-only
        assert not widget.notes_field.isReadOnly(), "Notes field should be editable"

        # Test that text can be set
        widget.notes_field.setPlainText("Test editing notes")
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == "Test editing notes"

    def test_set_sample_clears_notes_for_new_sample(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                    temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Test that setting sample to None clears notes field.

        Verifies that notes field is properly reset when switching to new sample.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create a sample with notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample",
            prompt_revision=prompt_revision,
            notes="Sample notes.",
        )

        assert sample is not None

        # Create widget with sample
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == "Sample notes."

        # Set to None (new sample)
        widget.set_sample(None)
        qt_app.processEvents()

        assert widget.notes_field.toPlainText() == ""
