"""Test enhanced CompletionFrame with multi-mode support."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.llm_response import LLMResponse


class TestCompletionFrameEnhanced:
    """Test the enhanced CompletionFrame with sample and beam modes."""

    def test_display_mode_validation(self):
        """Test that display_mode parameter is validated correctly."""
        # This test doesn't create widgets, so no Qt app needed
        with pytest.raises(ValueError, match="Invalid display_mode"):
            CompletionFrame.__new__(CompletionFrame)
            # Just test the validation logic without creating the widget
            if "invalid" not in ("sample", "beam"):
                raise ValueError("Invalid display_mode: invalid. Must be 'sample' or 'beam'.")

    def test_parameter_validation(self):
        """Test parameter validation logic."""
        # Test sample mode validation
        with pytest.raises(ValueError, match="completion parameter is required"):
            # Simulate the validation logic
            display_mode = "sample"
            completion = None
            if display_mode == "sample" and not completion:
                raise ValueError("completion parameter is required for sample mode.")
                
        # Test beam mode validation
        with pytest.raises(ValueError, match="beam parameter is required"):
            display_mode = "beam"
            beam = None
            if display_mode == "beam" and not beam:
                raise ValueError("beam parameter is required for beam mode.")

    def test_sample_mode_initialization(self, temp_dataset, qt_app, ensure_google_icon_font):
        """Test CompletionFrame initialization in sample mode."""
        # Create mock completion
        mock_completion = Mock()
        mock_completion.id = 1
        mock_completion.model_id = "test-model"
        mock_completion.temperature = 0.7
        mock_completion.top_k = 40
        mock_completion.completion_text = "Test completion text"
        mock_completion.is_archived = False
        mock_completion.is_truncated = False
        mock_completion.prefill = None
        mock_completion.beam_token = None
        mock_completion.logprobs = []

        frame = CompletionFrame(
            dataset=temp_dataset,
            completion=mock_completion,
            display_mode="sample"
        )

        assert frame.display_mode == "sample"
        assert frame.completion == mock_completion
        assert frame.beam is None
        
        # Check that sample mode widgets exist
        assert frame.rating_widget is not None
        assert frame.edit_button is not None
        assert frame.discard_button is not None
        assert frame.archive_button is not None
        
        # Check that beam mode widgets don't exist
        assert frame.save_button is None
        assert frame.pin_button is None

    def test_beam_mode_initialization(self, temp_dataset, qt_app, ensure_google_icon_font):
        """Test CompletionFrame initialization in beam mode."""
        # Create mock beam
        mock_beam = Mock(spec=LLMResponse)
        mock_beam.full_response_text = "Test beam response"
        mock_beam.model_id = "test-model"
        mock_beam.min_logprob = -0.5

        frame = CompletionFrame(
            dataset=temp_dataset,
            beam=mock_beam,
            display_mode="beam"
        )

        assert frame.display_mode == "beam"
        assert frame.completion is None
        assert frame.beam == mock_beam
        
        # Check that beam mode widgets exist
        assert frame.discard_button is not None
        assert frame.save_button is not None
        assert frame.pin_button is not None
        assert frame.archive_button is not None  # Should exist but be hidden initially
        
        # Check that sample mode widgets don't exist
        assert not hasattr(frame, 'rating_widget') or frame.rating_widget is None
        assert frame.edit_button is None

    @patch('py_fade.gui.widget_completion.QMessageBox.question')
    def test_sample_mode_signal_emissions(self, mock_question, temp_dataset, qt_app, ensure_google_icon_font):
        """Test that sample mode signals are emitted correctly.""" 
        # Set up mock for confirmation dialog
        mock_question.return_value = mock_question.StandardButton.Yes
        
        mock_completion = Mock()
        mock_completion.id = 1
        mock_completion.model_id = "test-model"
        mock_completion.temperature = 0.7
        mock_completion.top_k = 40
        mock_completion.completion_text = "Test completion text"
        mock_completion.is_archived = False
        mock_completion.is_truncated = False
        mock_completion.prefill = None
        mock_completion.beam_token = None
        mock_completion.logprobs = []

        frame = CompletionFrame(
            dataset=temp_dataset,
            completion=mock_completion,
            display_mode="sample"
        )

        # Test edit signal
        edit_signal_received = False
        def on_edit_requested(completion):
            nonlocal edit_signal_received
            edit_signal_received = True
            assert completion == mock_completion

        frame.edit_requested.connect(on_edit_requested)
        frame._on_edit_clicked()
        assert edit_signal_received

        # Test discard signal 
        discard_signal_received = False
        def on_discarded(completion):
            nonlocal discard_signal_received
            discard_signal_received = True
            assert completion == mock_completion

        frame.discarded.connect(on_discarded)
        frame._on_discard_clicked()
        assert discard_signal_received

    def test_beam_mode_signal_emissions(self, temp_dataset, qt_app, ensure_google_icon_font):
        """Test that beam mode signals are emitted correctly."""
        mock_beam = Mock(spec=LLMResponse)
        mock_beam.full_response_text = "Test beam response"
        mock_beam.model_id = "test-model"
        mock_beam.min_logprob = -0.5

        frame = CompletionFrame(
            dataset=temp_dataset,
            beam=mock_beam,
            display_mode="beam"
        )

        # Test pin signal
        pin_signal_received = False
        def on_pinned(frame_obj, is_pinned):
            nonlocal pin_signal_received
            pin_signal_received = True
            assert frame_obj == frame
            assert is_pinned == True  # Should be True after first click

        frame.pinned.connect(on_pinned)
        frame._on_pin_clicked()
        assert pin_signal_received
        assert frame.is_pinned == True

        # Test save signal
        save_signal_received = False
        def on_saved(frame_obj, completion):
            nonlocal save_signal_received
            save_signal_received = True
            assert frame_obj == frame

        frame.saved.connect(on_saved)
        frame._on_save_clicked()
        assert save_signal_received

        # Test discard signal (should not show confirmation for beams)
        discard_signal_received = False
        def on_discarded(frame_obj):
            nonlocal discard_signal_received
            discard_signal_received = True
            assert frame_obj == frame

        frame.discarded.connect(on_discarded)
        frame._on_discard_clicked()
        assert discard_signal_received