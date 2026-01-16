"""
Unit tests for beam mode resume functionality.

Tests the resume button visibility and behavior for both transient and persisted completions.
"""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from tests.helpers.data_helpers import (create_simple_llm_response, create_sample_with_truncated_completion,
                                        create_sample_with_archived_truncated_completion)
from tests.helpers.ui_helpers import (mock_three_way_editor, create_mock_mapped_model, create_transient_truncated_beam,
                                      assert_beam_frame_updated, setup_beam_generation_error_test, assert_beam_frame_unchanged,
                                      create_beam_widget_with_truncated_beam, create_beam_widget_with_sample_widget)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

logger = logging.getLogger(__name__)


class TestBeamModeResumeButton:
    """
    Test resume button visibility for beam mode completions.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_resume_button_hidden_for_non_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test resume button is hidden for non-truncated transient beams.
        """
        # Create a non-truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Complete beam text")
        beam.is_truncated = False

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Resume button should exist but be hidden
        assert frame.resume_button is not None
        assert frame.resume_button.isHidden()

    def test_resume_button_shown_for_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test resume button is shown for truncated transient beams.
        """
        # Create a truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Truncated beam")
        beam.is_truncated = True

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Resume button should be visible
        assert frame.resume_button is not None
        assert not frame.resume_button.isHidden()
        assert frame.resume_button.toolTip() == "Resume generation from this truncated completion."

    def test_resume_button_shown_for_truncated_saved_beam(self, temp_dataset):
        """
        Test resume button is shown for truncated saved beam completions.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create a completion frame in beam mode with saved completion
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Resume button should be visible
        assert frame.resume_button is not None
        assert not frame.resume_button.isHidden()

    def test_resume_button_hidden_for_archived_beam(self, temp_dataset):
        """
        Test resume button is hidden for archived beam completions even if truncated.
        """
        # Create a sample and truncated + archived completion
        _, completion = create_sample_with_archived_truncated_completion(temp_dataset)

        # Create a completion frame in beam mode
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Resume button should be hidden because it's archived
        assert frame.resume_button is not None
        assert frame.resume_button.isHidden()


class TestBeamModeResumeHandlers:
    """
    Test resume handlers in WidgetCompletionBeams.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_transient_beam_resume_updates_frame_with_continuation(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam generates continuation and updates the frame in place.
        """
        # Create widget
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a truncated transient beam
        truncated_beam = create_transient_truncated_beam()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)
        assert len(widget.beam_frames) == 1

        # Mock the text generation controller to return expanded completion
        expanded_beam = create_simple_llm_response("test-model", "Truncated expanded continuation")
        expanded_beam.is_truncated = False
        expanded_beam.context_length = 1024
        expanded_beam.max_tokens = 128

        mock_controller = MagicMock()
        mock_controller.generate_continuation.return_value = expanded_beam

        # Mock get_or_create_text_generation_controller
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger resume
        widget.on_beam_resume_requested(truncated_beam)

        # Verify the continuation was generated
        mock_controller.generate_continuation.assert_called_once()

        # Verify the beam frame was updated with the expanded completion
        assert_beam_frame_updated(widget, expanded_beam)

    def test_transient_beam_resume_handles_generation_failure(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam handles generation failures gracefully.
        """
        # Set up widget with error-raising controller
        widget, truncated_beam, _mock_controller = setup_beam_generation_error_test(app_with_dataset, monkeypatch)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger resume
            widget.on_beam_resume_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert_beam_frame_unchanged(widget, truncated_beam)

    def test_transient_beam_resume_handles_no_controller(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam handles missing controller gracefully.
        """
        # Create widget with truncated beam
        widget, truncated_beam, _mapped_model = create_beam_widget_with_truncated_beam(app_with_dataset)

        # Mock get_or_create_text_generation_controller to return None
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: None)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger resume
            widget.on_beam_resume_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert_beam_frame_unchanged(widget, truncated_beam)

    def test_persisted_beam_resume_opens_three_way_editor(self, app_with_dataset, temp_dataset, monkeypatch, qt_app):
        """
        Test that resuming a persisted beam opens the three-way editor.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create widget with sample widget
        widget, _mapped_model, _sample_widget = create_beam_widget_with_sample_widget(app_with_dataset)

        # Track if ThreeWayCompletionEditorWindow is created
        editor_instances = mock_three_way_editor(monkeypatch)

        # Trigger resume for persisted completion
        widget.on_beam_resume_requested(completion)
        qt_app.processEvents()

        # Verify the editor was created
        assert len(editor_instances) == 1

    def test_persisted_beam_resume_refreshes_sample_widget_on_success(self, app_with_dataset, temp_dataset, monkeypatch, qt_app):
        """
        Test that resuming a persisted beam refreshes the sample widget when editor returns success.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create widget with sample widget
        widget, _mapped_model, sample_widget = create_beam_widget_with_sample_widget(app_with_dataset)

        # Mock the editor and simulate success (return 1)
        _ = mock_three_way_editor(monkeypatch)
        from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow  # pylint: disable=import-outside-toplevel
        monkeypatch.setattr(ThreeWayCompletionEditorWindow, "exec", lambda self: 1)

        # Trigger resume for persisted completion
        widget.on_beam_resume_requested(completion)
        qt_app.processEvents()

        # Verify populate_outputs was called on sample widget
        sample_widget.populate_outputs.assert_called_once()
