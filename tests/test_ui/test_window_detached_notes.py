"""
Test Detached Notes Window functionality.

Tests for the detached notes window ensuring proper display, editing,
synchronization with main widget, and save functionality.
"""
import logging
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import QPlainTextEdit

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.window_detached_notes import DetachedNotesWindow

# Import all dataset models to ensure SQLAlchemy metadata is complete
# This is required for tests that use temp_dataset fixture
from py_fade.dataset import (  # pylint: disable=unused-import
    completion, completion_logprobs, completion_pairwise_ranks, completion_rating, export_template, facet, sample_tag, tag,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class TestDetachedNotesWindow:
    """Test detached notes window functionality."""

    # pylint: disable=unused-argument  # Fixtures are used by pytest

    def test_window_creation(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that detached notes window can be created.

        Verifies that the window is properly initialized and has expected components.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        assert window is not None
        assert window.isVisible()
        assert hasattr(window, "notes_editor")
        assert hasattr(window, "save_button")

    def test_window_is_non_modal(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that detached notes window is non-modal.

        Verifies that the window allows interaction with other windows.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        assert not window.isModal(), "Detached notes window should be non-modal"

    def test_notes_editor_exists(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes editor widget exists and is a QPlainTextEdit.

        Verifies the main editing component is present.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        assert hasattr(window, "notes_editor")
        assert isinstance(window.notes_editor, QPlainTextEdit)

    def test_save_button_exists(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that save button exists in the window.

        Verifies the save button is present for persisting changes.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        assert hasattr(window, "save_button")
        assert window.save_button is not None

    def test_initial_notes_displayed(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that initial notes are displayed in the editor.

        Verifies that notes passed to the window are shown.
        """
        initial_notes = "These are initial notes for testing."
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, initial_notes, None)
        window.show()
        qt_app.processEvents()

        assert window.notes_editor.toPlainText() == initial_notes

    def test_set_notes_updates_editor(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that set_notes method updates the editor content.

        Verifies that notes can be programmatically updated.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        new_notes = "New notes content"
        window.set_notes(new_notes)
        qt_app.processEvents()

        assert window.notes_editor.toPlainText() == new_notes

    def test_get_notes_returns_editor_content(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                              ensure_google_icon_font: None) -> None:
        """
        Test that get_notes returns current editor content.

        Verifies that notes can be retrieved from the editor.
        """
        initial_notes = "Test notes content"
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, initial_notes, None)
        window.show()
        qt_app.processEvents()

        assert window.get_notes() == initial_notes

    def test_save_button_disabled_initially(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                            ensure_google_icon_font: None) -> None:
        """
        Test that save button is disabled when no changes are made.

        Verifies that save button starts disabled.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        assert not window.save_button.isEnabled(), "Save button should be disabled initially"

    def test_save_button_enabled_after_edit(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                            ensure_google_icon_font: None) -> None:
        """
        Test that save button is enabled after editing notes.

        Verifies that modifying notes enables the save button.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        # Edit notes
        window.notes_editor.setPlainText("Modified notes")
        qt_app.processEvents()

        assert window.save_button.isEnabled(), "Save button should be enabled after editing"

    def test_notes_saved_signal_emitted(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that notes_saved signal is emitted when saving.

        Verifies signal emission for synchronization.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        # Track signal emission
        signal_received = []

        def on_notes_saved(notes: str):
            signal_received.append(notes)

        window.notes_saved.connect(on_notes_saved)

        # Edit and save notes
        new_notes = "Notes to save"
        window.notes_editor.setPlainText(new_notes)
        qt_app.processEvents()

        window.save_notes()
        qt_app.processEvents()

        assert len(signal_received) == 1
        assert signal_received[0] == new_notes

    def test_save_with_existing_sample(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                       temp_dataset: "DatasetDatabase") -> None:
        """
        Test that saving notes with existing sample persists to database.

        Verifies database update when sample exists.
        """
        # Create a sample
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(temp_dataset, title="Test Sample", prompt_revision=prompt_revision)

        assert sample is not None
        sample_id = sample.id

        # Create window with sample
        window = DetachedNotesWindow(temp_dataset, sample, "", None)
        window.show()
        qt_app.processEvents()

        # Edit and save notes
        new_notes = "Saved notes content"
        window.notes_editor.setPlainText(new_notes)
        qt_app.processEvents()

        window.save_notes()
        qt_app.processEvents()

        # Verify database was updated
        temp_dataset.session.expire_all()
        reloaded_sample = temp_dataset.session.query(Sample).filter_by(id=sample_id).first()
        assert reloaded_sample is not None
        assert reloaded_sample.notes == new_notes

    def test_save_without_sample(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that saving notes without sample emits signal but doesn't crash.

        Verifies behavior when sample is not yet saved.
        """
        caplog.set_level(logging.DEBUG, logger="DetachedNotesWindow")

        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        # Track signal emission
        signal_received = []
        window.notes_saved.connect(signal_received.append)

        # Edit and save notes
        new_notes = "Notes without sample"
        window.notes_editor.setPlainText(new_notes)
        qt_app.processEvents()

        window.save_notes()
        qt_app.processEvents()

        # Signal should still be emitted
        assert len(signal_received) == 1
        assert signal_received[0] == new_notes

    def test_close_event_emits_signal_if_modified(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                  ensure_google_icon_font: None) -> None:
        """
        Test that closing window with unsaved changes emits signal.

        Verifies synchronization happens even if user doesn't explicitly save.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        # Track signal emission
        signal_received = []
        window.notes_saved.connect(signal_received.append)

        # Edit notes without saving
        modified_notes = "Modified but not saved"
        window.notes_editor.setPlainText(modified_notes)
        qt_app.processEvents()

        # Close window
        window.close()
        qt_app.processEvents()

        # Signal should be emitted with current content
        assert len(signal_received) == 1
        assert signal_received[0] == modified_notes

    def test_close_event_no_signal_if_not_modified(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                   ensure_google_icon_font: None) -> None:
        """
        Test that closing window without changes doesn't emit extra signal.

        Verifies signal is only emitted when there are actual changes.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "Initial content", None)
        window.show()
        qt_app.processEvents()

        # Track signal emission
        signal_received = []
        window.notes_saved.connect(signal_received.append)

        # Close window without editing
        window.close()
        qt_app.processEvents()

        # Signal should not be emitted since nothing changed
        assert len(signal_received) == 0

    def test_save_button_disabled_after_save(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                             ensure_google_icon_font: None) -> None:
        """
        Test that save button is disabled after saving.

        Verifies button state management after save operation.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        # Edit notes
        window.notes_editor.setPlainText("Notes to save")
        qt_app.processEvents()
        assert window.save_button.isEnabled()

        # Save notes
        window.save_notes()
        qt_app.processEvents()

        # Save button should be disabled after save
        assert not window.save_button.isEnabled()

    def test_empty_notes_saved_as_empty_string(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                               ensure_google_icon_font: None) -> None:
        """
        Test that empty notes are saved as empty string in signal.

        Verifies handling of empty notes content.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "Initial notes", None)
        window.show()
        qt_app.processEvents()

        # Track signal emission
        signal_received = []
        window.notes_saved.connect(signal_received.append)

        # Clear notes and save
        window.notes_editor.setPlainText("")
        qt_app.processEvents()

        window.save_notes()
        qt_app.processEvents()

        assert len(signal_received) == 1
        assert signal_received[0] == ""

    def test_multiline_notes_preserved(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that multiline notes content is preserved.

        Verifies that newlines and formatting are maintained.
        """
        multiline_notes = "Line 1: First line\nLine 2: Second line\nLine 3: Third line"
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, multiline_notes, None)
        window.show()
        qt_app.processEvents()

        assert window.get_notes() == multiline_notes
        assert "\n" in window.get_notes()

    def test_window_title_set(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that window title is properly set.

        Verifies window has descriptive title.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        title = window.windowTitle()
        assert title
        assert "notes" in title.lower() or "editor" in title.lower()

    def test_window_minimum_size(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that window has reasonable minimum size.

        Verifies window is large enough for comfortable editing.
        """
        window = DetachedNotesWindow(app_with_dataset.current_dataset, None, "", None)
        window.show()
        qt_app.processEvents()

        min_size = window.minimumSize()
        assert min_size.width() >= 600, "Window should have minimum width for comfortable editing"
        assert min_size.height() >= 400, "Window should have minimum height for comfortable editing"
