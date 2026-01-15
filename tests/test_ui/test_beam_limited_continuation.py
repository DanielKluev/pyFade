"""
Unit tests for beam mode limited continuation functionality.

Tests the limited continuation button visibility and behavior for unsaved truncated beams.
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
from tests.helpers.ui_helpers import (create_mock_mapped_model, create_transient_truncated_beam, assert_beam_frame_updated,
                                      setup_beam_generation_error_test, assert_beam_frame_unchanged, create_beam_widget_with_truncated_beam,
                                      create_beam_widget_with_sample_widget)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

logger = logging.getLogger(__name__)


class TestLimitedContinuationButtonVisibility:
    """
    Test limited continuation button visibility for beam mode completions.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_limited_continuation_button_hidden_for_non_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test limited continuation button is hidden for non-truncated transient beams.
        """
        # Create a non-truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Complete beam text")
        beam.is_truncated = False

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Limited continuation button should exist but be hidden
        assert frame.limited_continuation_button is not None
        assert frame.limited_continuation_button.isHidden()

    def test_limited_continuation_button_shown_for_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test limited continuation button is shown for truncated transient beams.
        """
        # Create a truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Truncated beam")
        beam.is_truncated = True

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Limited continuation button should be visible
        assert frame.limited_continuation_button is not None
        assert not frame.limited_continuation_button.isHidden()
        assert frame.limited_continuation_button.toolTip() == "Generate limited continuation (Depth tokens only)"

    def test_limited_continuation_button_hidden_for_truncated_saved_beam(self, temp_dataset):
        """
        Test limited continuation button is hidden for truncated saved beam completions.
        
        Limited continuation is only for unsaved beams.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create a completion frame in beam mode with saved completion
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Limited continuation button should be hidden because it's saved
        assert frame.limited_continuation_button is not None
        assert frame.limited_continuation_button.isHidden()

    def test_limited_continuation_button_hidden_for_archived_beam(self, temp_dataset):
        """
        Test limited continuation button is hidden for archived beam completions even if truncated and unsaved.
        """
        # Create a sample and truncated + archived completion
        _, completion = create_sample_with_archived_truncated_completion(temp_dataset)

        # Create a completion frame in beam mode
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Limited continuation button should be hidden because it's archived
        assert frame.limited_continuation_button is not None
        assert frame.limited_continuation_button.isHidden()

    def test_limited_continuation_button_not_in_sample_mode(self, temp_dataset):
        """
        Test limited continuation button doesn't exist in sample mode.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create a completion frame in sample mode
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="sample")

        # Limited continuation button should not exist in sample mode
        assert frame.limited_continuation_button is None


class TestLimitedContinuationHandler:
    """
    Test limited continuation handler in WidgetCompletionBeams.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_limited_continuation_generates_with_depth_tokens(self, app_with_dataset, monkeypatch):
        """
        Test that limited continuation uses the Depth spin value for max_tokens.
        """
        # Create widget
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Set depth to 15 tokens
        widget.depth_spin.setValue(15)

        # Create a truncated transient beam
        truncated_beam = create_transient_truncated_beam()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)
        assert len(widget.beam_frames) == 1

        # Mock the text generation controller to return expanded completion
        expanded_beam = create_simple_llm_response("test-model", "Truncated expanded")
        expanded_beam.is_truncated = True  # Still truncated after limited continuation
        expanded_beam.context_length = 1024
        expanded_beam.max_tokens = 15  # Should match depth value

        mock_controller = MagicMock()
        mock_controller.generate_continuation.return_value = expanded_beam

        # Mock get_or_create_text_generation_controller
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger limited continuation
        widget.on_beam_limited_continuation_requested(truncated_beam)

        # Verify the continuation was generated with limited max_tokens (15)
        mock_controller.generate_continuation.assert_called_once()
        call_kwargs = mock_controller.generate_continuation.call_args[1]
        assert call_kwargs['max_tokens'] == 15

        # Verify the beam frame was updated with the expanded completion
        assert len(widget.beam_frames) == 1
        updated_beam, updated_frame = widget.beam_frames[0]
        assert updated_beam is expanded_beam
        assert updated_frame.completion is expanded_beam

    def test_limited_continuation_updates_frame_in_place(self, app_with_dataset, monkeypatch):
        """
        Test that limited continuation updates the beam frame in place.
        """
        # Create widget
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Set depth to 20 tokens
        widget.depth_spin.setValue(20)

        # Create a truncated transient beam
        truncated_beam = create_transient_truncated_beam()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)

        # Mock the text generation controller
        expanded_beam = create_simple_llm_response("test-model", "Truncated with limited continuation")
        expanded_beam.is_truncated = False  # Completed within limit
        expanded_beam.context_length = 1024
        expanded_beam.max_tokens = 20

        mock_controller = MagicMock()
        mock_controller.generate_continuation.return_value = expanded_beam

        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger limited continuation
        widget.on_beam_limited_continuation_requested(truncated_beam)

        # Verify continuation was generated
        mock_controller.generate_continuation.assert_called_once()

        # Verify frame was updated
        assert_beam_frame_updated(widget, expanded_beam)

    def test_limited_continuation_handles_generation_failure(self, app_with_dataset, monkeypatch):
        """
        Test that limited continuation handles generation failures gracefully.
        """
        # Set up widget with error-raising controller
        widget, truncated_beam, _mock_controller = setup_beam_generation_error_test(app_with_dataset, monkeypatch)

        # Set depth
        widget.depth_spin.setValue(10)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger limited continuation
            widget.on_beam_limited_continuation_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert_beam_frame_unchanged(widget, truncated_beam)

    def test_limited_continuation_handles_no_controller(self, app_with_dataset, monkeypatch):
        """
        Test that limited continuation handles missing controller gracefully.
        """
        # Create widget with truncated beam
        widget, truncated_beam, _mapped_model = create_beam_widget_with_truncated_beam(app_with_dataset)

        # Set depth
        widget.depth_spin.setValue(10)

        # Mock get_or_create_text_generation_controller to return None
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: None)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger limited continuation
            widget.on_beam_limited_continuation_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert_beam_frame_unchanged(widget, truncated_beam)

    def test_limited_continuation_ignores_persisted_beams(self, app_with_dataset, temp_dataset, monkeypatch):
        """
        Test that limited continuation ignores persisted (saved) beams.
        """
        # Create a sample and truncated completion
        _, completion = create_sample_with_truncated_completion(temp_dataset)

        # Create widget with sample widget
        widget, _mapped_model, _sample_widget = create_beam_widget_with_sample_widget(app_with_dataset)

        # Mock controller to track if it's called
        mock_controller = MagicMock()

        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger limited continuation for persisted completion
        widget.on_beam_limited_continuation_requested(completion)

        # Verify the controller was NOT called
        mock_controller.generate_continuation.assert_not_called()

    def test_limited_continuation_can_still_be_truncated(self, app_with_dataset, monkeypatch):
        """
        Test that limited continuation can still result in a truncated completion if it hits the limit.
        """
        # Create widget
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Set depth to a small value
        widget.depth_spin.setValue(5)

        # Create a truncated transient beam
        truncated_beam = create_transient_truncated_beam()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)

        # Mock the text generation controller to return still-truncated completion
        expanded_beam = create_simple_llm_response("test-model", "Truncated with 5 more tokens but still truncated")
        expanded_beam.is_truncated = True  # Still truncated after limited continuation
        expanded_beam.context_length = 1024
        expanded_beam.max_tokens = 5

        mock_controller = MagicMock()
        mock_controller.generate_continuation.return_value = expanded_beam

        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger limited continuation
        widget.on_beam_limited_continuation_requested(truncated_beam)

        # Verify continuation was generated with limited tokens
        mock_controller.generate_continuation.assert_called_once()
        call_kwargs = mock_controller.generate_continuation.call_args[1]
        assert call_kwargs['max_tokens'] == 5

        # Verify frame was updated with still-truncated completion
        assert len(widget.beam_frames) == 1
        updated_beam, _updated_frame = widget.beam_frames[0]
        assert updated_beam is expanded_beam
        assert updated_beam.is_truncated is True
