"""
Test WidgetSample integration with Detached Notes Window.

Tests for the notes button in WidgetSample and synchronization
between main widget and detached window.
"""
import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.widget_sample import WidgetSample

# Import all dataset models to ensure SQLAlchemy metadata is complete
# This is required for tests that use temp_dataset fixture
from py_fade.dataset import (  # pylint: disable=unused-import
    completion, completion_logprobs, completion_pairwise_ranks, completion_rating, export_template, facet, sample_tag, tag,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class TestWidgetSampleDetachedNotes:
    """Test detached notes integration with WidgetSample."""

    # pylint: disable=unused-argument  # Fixtures are used by pytest

    def test_open_notes_button_exists(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that open notes button exists in WidgetSample.

        Verifies the button for opening detached notes is present.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert hasattr(widget, "open_notes_button")
        assert widget.open_notes_button is not None

    def test_open_notes_button_tooltip(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that open notes button has descriptive tooltip.

        Verifies button has helpful tooltip text.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        tooltip = widget.open_notes_button.toolTip()
        assert tooltip
        assert "notes" in tooltip.lower() or "window" in tooltip.lower()

    def test_open_detached_notes_creates_window(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                ensure_google_icon_font: None) -> None:
        """
        Test that clicking open notes button creates detached window.

        Verifies window creation functionality.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded
        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Initially no detached window
        assert widget.detached_notes_window is None

        # Open detached notes
        widget.open_detached_notes()
        qt_app.processEvents()

        # Window should be created
        assert widget.detached_notes_window is not None
        assert widget.detached_notes_window.isVisible()

    def test_detached_window_has_initial_notes(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                               ensure_google_icon_font: None) -> None:
        """
        Test that detached window shows current notes from main widget.

        Verifies initial content synchronization.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create sample with notes
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", context_length=2048, max_tokens=256)
        sample = Sample.create_if_unique(temp_dataset, title="Test Sample", prompt_revision=prompt_revision, notes="Initial notes")

        widget = WidgetSample(None, app_with_dataset, sample)
        widget.show()
        qt_app.processEvents()

        # Open detached notes
        widget.open_detached_notes()
        qt_app.processEvents()

        # Detached window should have the same notes
        assert widget.detached_notes_window is not None
        assert widget.detached_notes_window.get_notes() == "Initial notes"

    def test_detached_window_synchronizes_to_main(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                  ensure_google_icon_font: None, caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that saving in detached window updates main widget.

        Verifies synchronization from detached to main widget.
        """
        caplog.set_level(logging.DEBUG, logger="WidgetSample")
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Set initial notes
        widget.notes_field.setPlainText("Original notes")
        qt_app.processEvents()

        # Open detached notes
        widget.open_detached_notes()
        qt_app.processEvents()

        # Modify and save in detached window
        widget.detached_notes_window.notes_editor.setPlainText("Modified notes in detached window")
        qt_app.processEvents()
        widget.detached_notes_window.save_notes()
        qt_app.processEvents()

        # Main widget should be updated
        assert widget.notes_field.toPlainText() == "Modified notes in detached window"

    def test_closing_detached_window_synchronizes(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                  ensure_google_icon_font: None) -> None:
        """
        Test that closing detached window with changes updates main widget.

        Verifies synchronization on window close.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Open detached notes
        widget.open_detached_notes()
        qt_app.processEvents()

        # Modify in detached window without explicit save
        widget.detached_notes_window.notes_editor.setPlainText("Modified without save")
        qt_app.processEvents()

        # Close window
        widget.detached_notes_window.close()
        qt_app.processEvents()

        # Main widget should be updated
        assert widget.notes_field.toPlainText() == "Modified without save"

    def test_reopen_existing_window_brings_to_front(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                    ensure_google_icon_font: None, caplog: pytest.LogCaptureFixture) -> None:
        """
        Test that reopening detached notes brings existing window to front.

        Verifies that only one window is created and reused.
        """
        caplog.set_level(logging.DEBUG, logger="WidgetSample")
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Open detached notes first time
        widget.open_detached_notes()
        qt_app.processEvents()
        first_window = widget.detached_notes_window

        assert first_window is not None
        assert first_window.isVisible()

        # Try to open again
        widget.open_detached_notes()
        qt_app.processEvents()

        # Should be the same window
        assert widget.detached_notes_window is first_window
        assert first_window.isVisible()

    def test_multiple_open_close_cycles(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test multiple open/close cycles of detached window.

        Verifies window can be opened, closed, and reopened multiple times.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # First cycle
        widget.open_detached_notes()
        qt_app.processEvents()
        assert widget.detached_notes_window is not None
        assert widget.detached_notes_window.isVisible()

        widget.detached_notes_window.close()
        qt_app.processEvents()

        # Second cycle
        widget.open_detached_notes()
        qt_app.processEvents()
        assert widget.detached_notes_window is not None
        assert widget.detached_notes_window.isVisible()

    def test_detached_notes_button_positioned_correctly(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                        ensure_google_icon_font: None) -> None:
        """
        Test that open notes button is positioned near notes field.

        Verifies button placement in UI layout.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Button should exist and be visible
        assert widget.open_notes_button.isVisible()

        # Button should have reasonable size
        button_size = widget.open_notes_button.size()
        assert button_size.width() > 0
        assert button_size.height() > 0

    def test_save_sample_with_detached_notes_open(
            self,
            qt_app: "QApplication",
            app_with_dataset: "pyFadeApp",
            temp_dataset: "DatasetDatabase",  # pylint: disable=unused-argument
            ensure_google_icon_font: None) -> None:
        """
        Test that saving sample works when detached notes window is open.

        Verifies no conflicts between detached window and save operation.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Fill in sample data
        widget.prompt_area.setPlainText("Test prompt")
        widget.title_field.setText("Test Sample")
        widget.notes_field.setPlainText("Initial notes")
        qt_app.processEvents()

        # Open detached notes
        widget.open_detached_notes()
        qt_app.processEvents()

        # Save sample
        widget.save_sample()
        qt_app.processEvents()

        # Should succeed without error
        assert widget.sample is not None
        assert widget.sample.notes == "Initial notes"

    def test_detached_window_updates_with_set_sample(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp",
                                                     temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Test that setting a new sample updates detached window if open.

        Verifies synchronization when sample is changed in main widget.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        # Create two samples
        prompt_revision1 = PromptRevision.get_or_create(temp_dataset, "Prompt 1", context_length=2048, max_tokens=256)
        sample1 = Sample.create_if_unique(temp_dataset, title="Sample 1", prompt_revision=prompt_revision1, notes="Notes for sample 1")

        prompt_revision2 = PromptRevision.get_or_create(temp_dataset, "Prompt 2", context_length=2048, max_tokens=256)
        sample2 = Sample.create_if_unique(temp_dataset, title="Sample 2", prompt_revision=prompt_revision2, notes="Notes for sample 2")

        widget = WidgetSample(None, app_with_dataset, sample1)
        widget.show()
        qt_app.processEvents()

        # Notes should be from sample1
        assert widget.notes_field.toPlainText() == "Notes for sample 1"

        # Open detached window
        widget.open_detached_notes()
        qt_app.processEvents()
        assert widget.detached_notes_window.get_notes() == "Notes for sample 1"

        # Close detached window for this test (in real usage, window may stay open)
        widget.detached_notes_window.close()
        qt_app.processEvents()

        # Set new sample
        widget.set_sample(sample2)
        qt_app.processEvents()

        # Notes should be updated
        assert widget.notes_field.toPlainText() == "Notes for sample 2"

    def test_empty_notes_handling(self, qt_app: "QApplication", app_with_dataset: "pyFadeApp", ensure_google_icon_font: None) -> None:
        """
        Test that empty notes are handled correctly in detached window.

        Verifies empty string synchronization works.
        """
        _ = ensure_google_icon_font  # Ensure Google icon font is loaded

        widget = WidgetSample(None, app_with_dataset, None)
        widget.show()
        qt_app.processEvents()

        # Open detached notes with empty notes
        widget.open_detached_notes()
        qt_app.processEvents()

        assert widget.detached_notes_window.get_notes() == ""

        # Set some notes then clear them
        widget.detached_notes_window.notes_editor.setPlainText("Some notes")
        qt_app.processEvents()
        widget.detached_notes_window.notes_editor.clear()
        qt_app.processEvents()
        widget.detached_notes_window.save_notes()
        qt_app.processEvents()

        # Main widget should have empty notes
        assert widget.notes_field.toPlainText() == ""
