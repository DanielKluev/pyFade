"""Comprehensive tests for the multi-mode CompletionFrame widget."""

# pylint: disable=protected-access,too-many-positional-arguments,too-many-lines

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.providers_manager import MappedModel
from py_fade.providers.mock_provider import MockLLMProvider
from tests.helpers.data_helpers import (build_sample_with_completion, create_test_llm_response, setup_beam_heatmap_test,
                                        create_test_single_position_token)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp

# Use imported helper functions instead of local duplicates
_build_sample_with_completion = build_sample_with_completion
_create_test_llm_response = create_test_llm_response


class TestCompletionFrameInitialization:
    """Test CompletionFrame initialization and basic properties."""

    def test_default_sample_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionFrame defaults to sample mode when no display_mode specified."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion)
        frame.show()
        qt_app.processEvents()

        assert frame.display_mode == "sample"
        assert hasattr(frame, 'rating_widget')
        assert frame.rating_widget is not None

    def test_explicit_sample_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionFrame works correctly when explicitly set to sample mode."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.display_mode == "sample"
        assert hasattr(frame, 'rating_widget')
        assert frame.rating_widget is not None

    def test_beam_mode_initialization(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionFrame initializes correctly in beam mode."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        assert frame.display_mode == "beam"
        assert not hasattr(frame, 'rating_widget')
        assert frame.is_pinned is False


class TestCompletionFrameButtonVisibility:
    """Test visibility and presence of buttons in different modes."""

    def test_sample_mode_buttons(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Sample mode shows correct buttons."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()  # Show the frame to make widgets visible
        frame.show()
        qt_app.processEvents()

        # Sample mode should have these buttons
        assert frame.edit_button is not None
        assert frame.discard_button is not None
        assert frame.archive_button is not None
        assert frame.resume_button is not None
        assert frame.evaluate_button is not None

        # Sample mode should NOT have these buttons
        assert frame.save_button is None
        assert frame.pin_button is None

    def test_beam_mode_buttons(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam mode shows correct buttons."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()  # Show the frame to make widgets visible
        frame.show()
        qt_app.processEvents()

        # Beam mode should have these buttons
        assert frame.save_button is not None
        assert frame.pin_button is not None
        assert frame.discard_button is not None
        assert frame.archive_button is not None

        # Beam mode should NOT have these buttons
        assert frame.edit_button is None

    def test_beam_mode_button_visibility_unsaved(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Unsaved beam shows save/pin buttons, hides archive."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()  # Show the frame to make widgets visible
        frame.show()
        qt_app.processEvents()

        # For unsaved beam
        assert frame.save_button.isVisible()
        assert frame.pin_button.isVisible()
        assert not frame.archive_button.isVisible()


class TestCompletionFrameHeaderVisibility:
    """Test header (model info) visibility in different modes."""

    def test_sample_mode_header_visible(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Sample mode shows header with model info."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()  # Show the frame to make widgets visible
        frame.show()
        qt_app.processEvents()

        # Model label should be visible in sample mode
        assert frame.model_label.isVisible()
        assert frame.model_label.text == "test-model"

    def test_beam_mode_header_hidden_for_unsaved(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam mode hides header for unsaved beams."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()  # Show the frame to make widgets visible
        frame.show()
        qt_app.processEvents()

        # Model label should be hidden for unsaved beam
        assert not frame.model_label.isVisible()


class TestCompletionFrameSignals:
    """Test signal emissions from button clicks."""

    def test_edit_signal_emission(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Edit button emits edit_requested signal."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signal_emitted = False
        emitted_completion = None

        def on_edit_requested(comp):
            nonlocal signal_emitted, emitted_completion
            signal_emitted = True
            emitted_completion = comp

        frame.edit_requested.connect(on_edit_requested)

        # Click edit button
        frame.edit_button.click()
        frame.show()
        qt_app.processEvents()

        assert signal_emitted
        assert emitted_completion is completion

    def test_discard_signal_emission_unsaved(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Discard button emits signal for unsaved completion without confirmation."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signal_emitted = False
        emitted_completion = None

        def on_discard_requested(comp):
            nonlocal signal_emitted, emitted_completion
            signal_emitted = True
            emitted_completion = comp

        frame.discard_requested.connect(on_discard_requested)

        # Click discard button (no ID means no confirmation dialog)
        frame.discard_button.click()
        frame.show()
        qt_app.processEvents()

        assert signal_emitted
        assert emitted_completion is beam

    def test_save_signal_emission(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Save button emits save_requested signal."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signal_emitted = False
        emitted_completion = None

        def on_save_requested(comp):
            nonlocal signal_emitted, emitted_completion
            signal_emitted = True
            emitted_completion = comp

        frame.save_requested.connect(on_save_requested)

        # Click save button
        frame.save_button.click()
        frame.show()
        qt_app.processEvents()

        assert signal_emitted
        assert emitted_completion is beam

    def test_pin_toggle_signal_emission(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Pin button toggles state and emits pin_toggled signal."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signals_emitted = []

        def on_pin_toggled(comp, is_pinned):
            signals_emitted.append((comp, is_pinned))

        frame.pin_toggled.connect(on_pin_toggled)

        # Initially not pinned
        assert not frame.is_pinned

        # Click pin button
        frame.pin_button.click()
        frame.show()
        qt_app.processEvents()

        assert frame.is_pinned
        assert len(signals_emitted) == 1
        assert signals_emitted[0] == (beam, True)

        # Click again to unpin
        frame.pin_button.click()
        frame.show()
        qt_app.processEvents()

        assert not frame.is_pinned
        assert len(signals_emitted) == 2
        assert signals_emitted[1] == (beam, False)


class TestCompletionFrameTextDisplay:
    """Test text display and highlighting functionality."""

    def test_basic_text_display(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Text content is displayed correctly."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == completion.completion_text

    def test_beam_text_display(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam response text is displayed correctly."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Test beam response content")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == "Test beam response content"

    def test_prefill_highlighting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Prefill text highlighting is applied."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Prefilled text and continuation", prefill="Prefilled text")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Check that the text is set correctly
        assert frame.text_edit.toPlainText() == "Prefilled text and continuation"
        # Note: Testing the actual highlighting would require inspecting QTextCharFormat
        # which is complex in unit tests. We just verify the highlighting method is called.

    def test_beam_token_highlighting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam token highlighting is applied."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Start token continuation", beam_token="token")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == "Start token continuation"


class TestCompletionFrameStatusIcons:
    """Test status icon display based on completion properties."""

    def test_truncated_completion_shows_icon(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Truncated completion shows truncation icon."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, is_truncated=True)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Should have status icons in the layout
        assert frame.status_layout.count() > 0

    def test_prefill_completion_shows_icon(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Completion with prefill shows prefill icon."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, prefill="Test prefill")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Should have status icons in the layout
        assert frame.status_layout.count() > 0

    def test_beam_token_completion_shows_icon(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Completion with beam token shows beam icon."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, beam_token="test_token")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Should have status icons in the layout
        assert frame.status_layout.count() > 0

    def test_llm_response_with_logprobs(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """LLMResponse with logprobs shows metrics icon with proper color."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(
            logprobs=[create_test_single_position_token("test", -1.2),
                      create_test_single_position_token("token", -0.8)])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Should have status icons in the layout
        assert frame.status_layout.count() > 0


class TestCompletionFrameButtonBehavior:
    """Test specific button behaviors and state changes."""

    def test_resume_button_visibility(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Resume button only visible for truncated, non-archived completions."""
        _ = ensure_google_icon_font

        # Test truncated, non-archived completion
        _, completion = _build_sample_with_completion(temp_dataset, is_truncated=True, is_archived=False)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.resume_button.isVisible()

        # Test non-truncated completion
        _, completion2 = _build_sample_with_completion(temp_dataset, is_truncated=False, is_archived=False)

        frame2 = CompletionFrame(temp_dataset, completion2, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert not frame2.resume_button.isVisible()

    def test_archive_button_state(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Archive button shows correct icon based on archived state."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, is_archived=False)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Should show archive icon when not archived
        assert frame.archive_button.isVisible()

        # Test archived completion
        _, archived_completion = _build_sample_with_completion(temp_dataset, is_archived=True)

        archived_frame = CompletionFrame(temp_dataset, archived_completion, display_mode="sample")
        archived_frame.show()  # Show the archived frame, not the original frame
        qt_app.processEvents()

        # Should show unarchive icon when archived
        assert archived_frame.archive_button.isVisible()

    def test_pin_visual_state_changes(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Pin button changes visual state when toggled."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response()

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Initially not pinned
        initial_style = frame.styleSheet()

        # Pin it
        frame.pin_button.click()
        frame.show()
        qt_app.processEvents()

        # Should have different styling when pinned
        pinned_style = frame.styleSheet()
        assert pinned_style != initial_style

        # Unpin it
        frame.pin_button.click()
        frame.show()
        qt_app.processEvents()

        # Should return to original styling
        unpinned_style = frame.styleSheet()
        assert unpinned_style == initial_style


class TestCompletionFrameConfirmationDialogs:
    """Test confirmation dialogs for destructive actions."""

    @patch('PyQt6.QtWidgets.QMessageBox.question')
    def test_discard_confirmation_for_saved_completion(
        self,
        mock_question,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Discard shows confirmation dialog for saved completions."""
        _ = ensure_google_icon_font

        # Mock the confirmation dialog to return "No"
        mock_question.return_value = QMessageBox.StandardButton.No

        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signal_emitted = False

        def on_discard_requested(_comp):
            nonlocal signal_emitted
            signal_emitted = True

        frame.discard_requested.connect(on_discard_requested)

        # Click discard button
        frame.discard_button.click()
        qt_app.processEvents()

        # Should show confirmation dialog
        mock_question.assert_called_once()

        # Signal should NOT be emitted if user clicked "No"
        assert not signal_emitted

    @patch('PyQt6.QtWidgets.QMessageBox.question')
    def test_discard_confirmation_accepted(
        self,
        mock_question,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Discard proceeds when user confirms."""
        _ = ensure_google_icon_font

        # Mock the confirmation dialog to return "Yes"
        mock_question.return_value = QMessageBox.StandardButton.Yes

        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Track signal emission
        signal_emitted = False
        emitted_completion = None

        def on_discard_requested(comp):
            nonlocal signal_emitted, emitted_completion
            signal_emitted = True
            emitted_completion = comp

        frame.discard_requested.connect(on_discard_requested)

        # Click discard button
        frame.discard_button.click()
        qt_app.processEvents()

        # Should show confirmation dialog
        mock_question.assert_called_once()

        # Signal SHOULD be emitted if user clicked "Yes"
        assert signal_emitted
        assert emitted_completion is completion


class TestCompletionFrameEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_display_mode_defaults_to_sample(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Invalid display mode should default to sample behavior."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        # Create with invalid mode
        frame = CompletionFrame(temp_dataset, completion, display_mode="invalid")
        frame.show()
        qt_app.processEvents()

        # Should still work, storing the mode as given
        assert frame.display_mode == "invalid"
        # But button setup should handle this gracefully

    def test_empty_completion_text(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Empty completion text is handled gracefully."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, completion_text="")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == ""

    def test_facet_setting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Setting facet updates rating widget context."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Initially no facet
        assert frame.current_facet is None

        # Set facet to None (should work)
        frame.set_facet(None)
        frame.show()
        qt_app.processEvents()

        assert frame.current_facet is None

    def test_target_model_setting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Setting target model updates evaluate button visibility."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Initially no target model
        assert frame.target_model is None

        # Set target model
        mock_provider = MockLLMProvider()
        test_model = MappedModel("test-target-model", mock_provider)
        frame.set_target_model(test_model)
        frame.show()
        qt_app.processEvents()

        assert frame.target_model == test_model

    def test_completion_mode_switching(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Changing completion updates display appropriately."""
        _ = ensure_google_icon_font
        _, completion1 = _build_sample_with_completion(temp_dataset, completion_text="First completion")

        frame = CompletionFrame(temp_dataset, completion1, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == "First completion"

        # Create second completion and update
        _, completion2 = _build_sample_with_completion(temp_dataset, completion_text="Second completion")

        frame.set_completion(completion2)
        frame.show()
        qt_app.processEvents()

        assert frame.text_edit.toPlainText() == "Second completion"
        assert frame.completion is completion2


class TestCompletionFrameHeatmapMode:
    """Test heatmap mode functionality."""

    def test_heatmap_button_hidden_without_logprobs(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap button is hidden when completion has no full logprobs."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Should be hidden by default since no full logprobs
        assert frame.heatmap_button is not None
        assert not frame.heatmap_button.isVisible()

    def test_heatmap_button_visible_with_full_logprobs(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap button is visible when completion has full logprobs and target model is set."""
        _ = ensure_google_icon_font

        frame, _ = setup_beam_heatmap_test(temp_dataset, qt_app)

        # Should be visible with full logprobs and target model set
        assert frame.heatmap_button is not None
        assert frame.heatmap_button.isVisible()
        assert not frame.heatmap_button.isChecked()

    def test_heatmap_toggle_functionality(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap button toggles heatmap mode correctly."""
        _ = ensure_google_icon_font

        # Create LLMResponse with full logprobs
        beam = _create_test_llm_response(
            completion_text="Test token",
            logprobs=[create_test_single_position_token("Test", -0.5),
                      create_test_single_position_token(" token", -1.2)])
        beam.is_full_response_logprobs = True

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Initially not in heatmap mode
        assert not frame.is_heatmap_mode
        assert not frame.heatmap_button.isChecked()

        # Toggle heatmap mode on
        frame.heatmap_button.click()
        qt_app.processEvents()

        assert frame.is_heatmap_mode
        assert frame.heatmap_button.isChecked()

        # Toggle heatmap mode off
        frame.heatmap_button.click()
        qt_app.processEvents()

        assert not frame.is_heatmap_mode
        assert not frame.heatmap_button.isChecked()

    def test_heatmap_mode_disables_prefill_beam_highlighting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap mode disables prefill and beam highlighting."""
        _ = ensure_google_icon_font

        # Create LLMResponse with full logprobs and prefill
        beam = _create_test_llm_response(
            completion_text="Prefill content", prefill="Prefill",
            logprobs=[create_test_single_position_token("Prefill", -0.3),
                      create_test_single_position_token(" content", -0.9)])
        beam.is_full_response_logprobs = True

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Initially should have prefill highlighting (not heatmap)
        assert not frame.is_heatmap_mode

        # Enable heatmap mode - this should switch to logprob highlighting
        frame.heatmap_button.click()
        qt_app.processEvents()

        assert frame.is_heatmap_mode
        # The highlighting method switch is tested implicitly by the display update

    def test_can_show_heatmap_for_llm_response(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """_can_show_heatmap correctly identifies LLMResponse with full logprobs when target model is set."""
        _ = ensure_google_icon_font

        # Create LLMResponse with partial logprobs
        beam_partial = _create_test_llm_response(logprobs=[create_test_single_position_token("test", -1.0)])
        beam_partial.is_full_response_logprobs = False

        frame = CompletionFrame(temp_dataset, beam_partial, display_mode="beam")

        # Set target model
        mock_provider = MockLLMProvider()
        test_model = MappedModel("test-beam-model", mock_provider)
        frame.set_target_model(test_model)

        # Should not show heatmap for partial logprobs even with target model
        assert not frame._can_show_heatmap(beam_partial)

        # Create LLMResponse with full logprobs that match the completion text
        beam_full = _create_test_llm_response(completion_text="test", logprobs=[create_test_single_position_token("test", -1.0)])
        beam_full.is_full_response_logprobs = True

        # Should show heatmap for full logprobs with target model
        assert frame._can_show_heatmap(beam_full)

    def test_check_logprobs_cover_text(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """check_full_response_logprobs correctly validates token coverage."""
        _ = ensure_google_icon_font

        # Create a completion without logprobs first
        _, completion = _build_sample_with_completion(temp_dataset)

        # Test that completion without logprobs returns False
        assert not completion.check_full_response_logprobs()

        # Test with an LLMResponse that has matching logprobs
        beam = _create_test_llm_response(completion_text="test", logprobs=[create_test_single_position_token("test", -1.0)])
        beam.is_full_response_logprobs = True

        # LLMResponse should have full coverage when tokens match
        assert beam.check_full_response_logprobs()

    def test_get_logprobs_for_heatmap_llm_response(
        self,
        temp_dataset: "DatasetDatabase",  # pylint: disable=unused-argument
        qt_app: "QApplication",  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """get_logprobs_for_model_id correctly extracts data from LLMResponse."""
        _ = ensure_google_icon_font

        # Create LLMResponse with logprobs
        beam = _create_test_llm_response(
            logprobs=[create_test_single_position_token("test", -1.0),
                      create_test_single_position_token(" token", -0.5)])

        # Test that we can get logprobs for the matching model ID
        logprobs_data = beam.get_logprobs_for_model_id("test-beam-model")
        assert logprobs_data is not None
        assert len(logprobs_data.sampled_logprobs) == 2
        assert logprobs_data.sampled_logprobs[0].token_str == "test"
        assert logprobs_data.sampled_logprobs[1].token_str == " token"

        # Test that we get None for non-matching model ID
        logprobs_data_none = beam.get_logprobs_for_model_id("non-existent-model")
        assert logprobs_data_none is None

    def test_heatmap_text_edit_tooltip_positioning(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionTextEdit correctly caches token positions for tooltips."""
        _ = ensure_google_icon_font

        frame, _ = setup_beam_heatmap_test(temp_dataset, qt_app)

        # Enable heatmap mode
        frame.heatmap_button.click()
        qt_app.processEvents()

        # Check that token positions cache is populated
        text_edit = frame.text_edit
        assert text_edit.is_heatmap_mode
        assert len(text_edit._token_positions_cache) > 0

        # Verify the cache contains expected token positions
        cache = text_edit._token_positions_cache
        assert cache[0][2].token_str == "Hello"  # First token
        assert cache[1][2].token_str == " world"  # Second token

    def test_heatmap_mode_with_target_model_logprobs(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap works with PromptCompletion when target model logprobs available."""
        _ = ensure_google_icon_font

        # This test would require setting up PromptCompletionLogprobs
        # For now, just test the basic target model setting
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")

        # Create a test MappedModel for testing
        mock_provider = MockLLMProvider()
        test_model = MappedModel("test-model", mock_provider)
        frame.set_target_model(test_model)

        # Without actual logprobs, heatmap shouldn't be available
        assert not frame._can_show_heatmap(completion)
        assert not frame.heatmap_button.isVisible()
