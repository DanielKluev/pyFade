"""Tests for beam-out from heatmap feature."""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from py_fade.providers.mock_provider import MockLLMProvider
from py_fade.providers.providers_manager import MappedModel
from tests.helpers.data_helpers import create_test_llm_response, create_test_single_position_token
from tests.helpers.ui_helpers import setup_completion_frame_with_heatmap

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import PyFadeApp


class TestHeatmapTokenClick:
    """Test mouse click handling on heatmap tokens."""

    def test_mouse_click_in_heatmap_mode_triggers_signal(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Mouse click on token in heatmap mode triggers beam_out_requested signal."""
        _ = ensure_google_icon_font
        # Create completion with logprobs
        beam = create_test_llm_response(
            completion_text="Hello world",
            logprobs=[create_test_single_position_token("Hello", -0.1),
                      create_test_single_position_token(" world", -0.8)])

        frame, text_edit = setup_completion_frame_with_heatmap(temp_dataset, beam, qt_app)

        # Ensure cache is populated (should be done by helper, but let's be explicit)
        assert len(text_edit._token_positions_cache) > 0, "Token positions cache should be populated"

        # Connect signal to capture emission
        signal_emitted = []

        def capture_signal(token_index: int):
            signal_emitted.append(token_index)

        frame.beam_out_requested.connect(capture_signal)

        # Simulate mouse click at position 2 (in "Hello" token, index 0)
        cursor = text_edit.textCursor()
        cursor.setPosition(2)
        text_edit.setTextCursor(cursor)

        # Create mouse press event at position 2
        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),  # Arbitrary position
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)

        # Mock cursorForPosition to return cursor at position 2
        with patch.object(text_edit, 'cursorForPosition', return_value=cursor):
            text_edit.mousePressEvent(mock_event)

        # Verify signal was emitted with token index 0 (first token)
        assert len(signal_emitted) == 1
        assert signal_emitted[0] == 0

    def test_mouse_click_non_heatmap_mode_no_signal(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Mouse click in non-heatmap mode does not trigger signal."""
        _ = ensure_google_icon_font
        beam = create_test_llm_response(completion_text="Hello world")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        # Not in heatmap mode
        assert not text_edit.is_heatmap_mode

        # Connect signal to capture emission
        signal_emitted = []
        frame.beam_out_requested.connect(signal_emitted.append)

        # Simulate mouse click
        cursor = text_edit.textCursor()
        cursor.setPosition(2)

        mock_event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                                 Qt.KeyboardModifier.NoModifier)

        with patch.object(text_edit, 'cursorForPosition', return_value=cursor):
            text_edit.mousePressEvent(mock_event)

        # Verify no signal was emitted
        assert len(signal_emitted) == 0

    def test_mouse_click_right_button_no_signal(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Right mouse button click does not trigger signal."""
        _ = ensure_google_icon_font
        beam = create_test_llm_response(
            completion_text="Hello world",
            logprobs=[create_test_single_position_token("Hello", -0.1),
                      create_test_single_position_token(" world", -0.8)])

        frame, text_edit = setup_completion_frame_with_heatmap(temp_dataset, beam, qt_app)

        # Connect signal to capture emission
        signal_emitted = []
        frame.beam_out_requested.connect(signal_emitted.append)

        # Simulate right mouse button click
        cursor = text_edit.textCursor()
        cursor.setPosition(2)

        mock_event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
                                 Qt.KeyboardModifier.NoModifier)

        with patch.object(text_edit, 'cursorForPosition', return_value=cursor):
            text_edit.mousePressEvent(mock_event)

        # Verify no signal was emitted
        assert len(signal_emitted) == 0


class TestBeamOutHandler:
    """Test beam-out handler in WidgetCompletionBeams."""

    def test_beam_out_handler_extracts_correct_prefix(
        self,
        app_with_dataset: "PyFadeApp",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam-out handler extracts correct prefix before clicked token."""
        _ = ensure_google_icon_font
        # Create beam widget
        mapped_model = MappedModel("mock-echo-model", MockLLMProvider())

        widget = WidgetCompletionBeams(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=None,
            mapped_model=mapped_model,
        )
        widget.show()
        qt_app.processEvents()

        # Create a beam with logprobs
        beam = create_test_llm_response(
            completion_text="Red lazy fox", logprobs=[
                create_test_single_position_token("Red", -0.1),
                create_test_single_position_token(" lazy", -0.2),
                create_test_single_position_token(" fox", -0.3),
            ])

        # Add beam to widget
        widget.add_beam_frame(beam)

        # Find the frame
        _, frame = widget.beam_frames[0]

        # Mock _show_beam_out_token_picker to capture the prefix
        captured_prefix = []

        def capture_prefix(token_logprobs, prefix_text):  # pylint: disable=unused-argument
            captured_prefix.append(prefix_text)

        with patch.object(widget, '_show_beam_out_token_picker', side_effect=capture_prefix):
            # Mock the beam controller
            mock_controller = MagicMock()
            mock_controller.fetch_next_token_logprobs_for_prefix.return_value = []
            with patch.object(widget, '_get_or_create_beam_controller', return_value=mock_controller):
                # Trigger beam-out at token index 2 (the " fox" token)
                frame.on_heatmap_token_clicked(2)
                qt_app.processEvents()

        # Verify prefix is "Red lazy" (tokens before index 2)
        assert len(captured_prefix) == 1
        assert captured_prefix[0] == "Red lazy"

    def test_beam_out_handler_calls_token_picker(
        self,
        app_with_dataset: "PyFadeApp",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam-out handler calls token picker with alternatives."""
        _ = ensure_google_icon_font
        # Create beam widget
        mapped_model = MappedModel("mock-echo-model", MockLLMProvider())

        widget = WidgetCompletionBeams(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=None,
            mapped_model=mapped_model,
        )
        widget.show()
        qt_app.processEvents()

        # Create a beam with logprobs
        beam = create_test_llm_response(
            completion_text="Test completion", logprobs=[
                create_test_single_position_token("Test", -0.1),
                create_test_single_position_token(" completion", -0.2),
            ])

        widget.add_beam_frame(beam)
        _, frame = widget.beam_frames[0]

        # Mock the beam controller to return token alternatives
        mock_controller = MagicMock()
        mock_alternatives = [
            create_test_single_position_token(" completion", -0.2),
            create_test_single_position_token(" result", -0.5),
            create_test_single_position_token(" output", -0.7),
        ]
        mock_controller.fetch_next_token_logprobs_for_prefix.return_value = mock_alternatives

        # Mock _show_beam_out_token_picker to verify it's called
        picker_called = []

        def capture_picker_call(token_logprobs, prefix_text):  # pylint: disable=unused-argument
            picker_called.append((token_logprobs, prefix_text))

        with patch.object(widget, '_get_or_create_beam_controller', return_value=mock_controller):
            with patch.object(widget, '_show_beam_out_token_picker', side_effect=capture_picker_call):
                # Trigger beam-out at token index 1
                frame.on_heatmap_token_clicked(1)
                qt_app.processEvents()

        # Verify token picker was called
        assert len(picker_called) == 1
        token_logprobs, prefix_text = picker_called[0]
        assert token_logprobs == mock_alternatives
        assert prefix_text == "Test"

    def test_beam_out_handler_invalid_token_index(
        self,
        app_with_dataset: "PyFadeApp",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam-out handler handles invalid token index gracefully."""
        _ = ensure_google_icon_font
        # Create beam widget
        mapped_model = MappedModel("mock-echo-model", MockLLMProvider())

        widget = WidgetCompletionBeams(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=None,
            mapped_model=mapped_model,
        )
        widget.show()
        qt_app.processEvents()

        # Create a beam with logprobs
        beam = create_test_llm_response(completion_text="Test", logprobs=[create_test_single_position_token("Test", -0.1)])

        widget.add_beam_frame(beam)

        # Mock _show_beam_out_token_picker to verify it's not called
        picker_called = []

        def capture_picker_call(token_logprobs, prefix_text):  # pylint: disable=unused-argument
            picker_called.append(True)

        with patch.object(widget, '_show_beam_out_token_picker', side_effect=capture_picker_call):
            # Trigger beam-out with out-of-bounds index
            widget.on_beam_out_requested(10)  # Index 10 is invalid (only 1 token)
            qt_app.processEvents()

        # Verify token picker was not called
        assert len(picker_called) == 0

    def test_beam_out_token_selection_starts_generation(
        self,
        app_with_dataset: "PyFadeApp",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Selecting tokens in beam-out picker starts beam generation."""
        _ = ensure_google_icon_font
        # Create beam widget
        mapped_model = MappedModel("mock-echo-model", MockLLMProvider())

        widget = WidgetCompletionBeams(
            parent=None,
            app=app_with_dataset,
            prompt="Test prompt",
            sample_widget=None,
            mapped_model=mapped_model,
        )
        widget.show()
        qt_app.processEvents()

        # Create selected tokens
        selected_tokens = [
            create_test_single_position_token(" fox", -0.3),
            create_test_single_position_token(" dog", -0.5),
        ]

        # Mock _generate_beams_with_tokens to verify it's called
        generation_called = []

        def capture_generation(beam_tokens):
            generation_called.append(beam_tokens)

        # Create a mock dialog
        mock_dialog = MagicMock(spec=QDialog)

        with patch.object(widget, '_generate_beams_with_tokens', side_effect=capture_generation):
            # Call the handler directly
            widget._on_beam_out_tokens_selected(selected_tokens, prefix_text="Red lazy", dialog=mock_dialog)
            qt_app.processEvents()

        # Verify generation was called with selected tokens
        assert len(generation_called) == 1
        assert generation_called[0] == selected_tokens

        # Verify prefill was set
        assert widget.prefill_edit.toPlainText() == "Red lazy"


class TestCompletionFrameBeamOutMethod:
    """Test the on_heatmap_token_clicked method in CompletionFrame."""

    def test_on_heatmap_token_clicked_emits_signal(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """on_heatmap_token_clicked method emits beam_out_requested signal."""
        _ = ensure_google_icon_font
        beam = create_test_llm_response(completion_text="Test")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        # Connect signal to capture emission
        signal_emitted = []
        frame.beam_out_requested.connect(signal_emitted.append)

        # Call the method
        frame.on_heatmap_token_clicked(5)

        # Verify signal was emitted with correct index
        assert signal_emitted == [5]
