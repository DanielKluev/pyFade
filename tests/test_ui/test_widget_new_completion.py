"""
Comprehensive tests for the extended NewCompletionFrame widget.

Tests all four modes: REGULAR, CONTINUATION, MANUAL, and TOKEN_BY_TOKEN.
"""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QWidget

from py_fade.gui.widget_new_completion import NewCompletionFrame, CompletionMode
from py_fade.data_formats.base_data_classes import SinglePositionTopLogprobs
from tests.helpers.data_helpers import (build_sample_with_completion, create_test_llm_response, create_test_single_position_token,
                                        create_mock_widget_sample)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


class TestNewCompletionFrameInitialization:
    """
    Test NewCompletionFrame initialization and basic properties.
    """

    def test_default_initialization(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", ensure_google_icon_font: None) -> None:
        """
        NewCompletionFrame initializes with default mode (REGULAR).
        
        Flow:
        1. Create NewCompletionFrame with app
        2. Verify default mode is REGULAR
        3. Verify all UI elements are created
        
        Edge cases tested:
        - Default values are set correctly
        - All required widgets exist
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.REGULAR
        assert frame.generated_completion is None
        assert frame.current_completion is None
        assert frame.token_by_token_prefix == ""
        assert not frame.token_by_token_tokens

        # Check UI elements exist
        assert hasattr(frame, 'mode_combo')
        assert hasattr(frame, 'model_combo')
        assert hasattr(frame, 'temp_spin')
        assert hasattr(frame, 'topk_spin')
        assert hasattr(frame, 'prefill_edit')
        assert hasattr(frame, 'completion_area')
        assert hasattr(frame, 'token_picker_area')
        assert hasattr(frame, 'generate_btn')
        assert hasattr(frame, 'save_btn')
        assert hasattr(frame, 'continue_generation_btn')
        assert hasattr(frame, 'manual_model_id_edit')

    def test_mode_combo_has_all_modes(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", ensure_google_icon_font: None) -> None:
        """
        Mode combo box contains all four modes.
        
        Flow:
        1. Create NewCompletionFrame
        2. Check mode combo has 4 items
        3. Verify each mode is present
        
        Edge cases tested:
        - All modes are available for selection
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        assert frame.mode_combo.count() == 4
        modes = []
        for i in range(frame.mode_combo.count()):
            modes.append(frame.mode_combo.itemData(i))

        assert CompletionMode.REGULAR in modes
        assert CompletionMode.CONTINUATION in modes
        assert CompletionMode.MANUAL in modes
        assert CompletionMode.TOKEN_BY_TOKEN in modes


class TestNewCompletionFrameModeSwitching:
    """
    Test mode switching behavior.
    """

    def test_switch_to_manual_mode(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", ensure_google_icon_font: None) -> None:
        """
        Switching to MANUAL mode updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame in default mode
        2. Switch to MANUAL mode
        3. Verify UI elements are updated
        
        Edge cases tested:
        - Completion area becomes editable
        - Manual model ID field exists and is accessible
        - Prefill area is disabled
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to manual mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.MANUAL:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.MANUAL
        assert not frame.completion_area.isReadOnly()
        assert not frame.prefill_edit.isEnabled()
        # Manual model ID field should exist and be functional
        assert frame.manual_model_id_edit is not None
        assert frame.manual_model_id_edit.text() == "manual"  # Default value

    def test_switch_to_token_by_token_mode(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                          ensure_google_icon_font: None) -> None:
        """
        Switching to TOKEN_BY_TOKEN mode updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame
        2. Switch to TOKEN_BY_TOKEN mode
        3. Verify token picker area visibility
        
        Edge cases tested:
        - Generate button text changes
        - Token picker area can be shown
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.TOKEN_BY_TOKEN:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.TOKEN_BY_TOKEN
        assert frame.generate_btn.text() == "Next Token"

    def test_switch_to_continuation_mode(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                        ensure_google_icon_font: None) -> None:
        """
        Switching to CONTINUATION mode updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame
        2. Switch to CONTINUATION mode
        3. Verify button text changes
        
        Edge cases tested:
        - Generate button text changes to "Continue"
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to continuation mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.CONTINUATION:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.CONTINUATION
        assert frame.generate_btn.text() == "Continue"


class TestNewCompletionFrameRegularMode:
    """
    Test regular generation mode.
    """

    def test_regular_generation_success(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                       ensure_google_icon_font: None) -> None:
        """
        Regular generation mode generates completion successfully.
        
        Flow:
        1. Create NewCompletionFrame with mock widget sample
        2. Trigger regular generation
        3. Verify completion is generated and displayed
        
        Edge cases tested:
        - Controller is created correctly
        - Completion is generated with correct parameters
        - Display is updated
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Mock the controller and generation
        mock_controller = MagicMock()
        mock_response = create_test_llm_response(
            model_id="mock-echo-model",
            completion_text="This is a test completion",
            prefill="Test prefill",
        )
        mock_controller.generate.return_value = mock_response

        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.prefill_edit.setPlainText("Test prefill")
            frame.generate_completion()
            qt_app.processEvents()

        assert frame.generated_completion is not None
        assert frame.generated_completion.completion_text == "This is a test completion"
        assert frame.save_btn.isEnabled()

    def test_regular_generation_with_empty_prefill(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                   temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Regular generation works with empty prefill.
        
        Flow:
        1. Create NewCompletionFrame
        2. Leave prefill empty
        3. Trigger generation
        4. Verify completion is generated
        
        Edge cases tested:
        - Empty prefill is handled correctly
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        mock_controller = MagicMock()
        mock_response = create_test_llm_response(
            model_id="mock-echo-model",
            completion_text="Completion without prefill",
            prefill=None,
        )
        mock_controller.generate.return_value = mock_response

        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.generate_completion()
            qt_app.processEvents()

        assert frame.generated_completion is not None
        assert frame.generated_completion.prefill is None


class TestNewCompletionFrameManualMode:
    """
    Test manual completion input mode.
    """

    def test_manual_completion_with_custom_model_id(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                    ensure_google_icon_font: None) -> None:
        """
        Manual mode creates completion with custom model ID.
        
        Flow:
        1. Switch to manual mode
        2. Enter completion text and custom model ID
        3. Trigger save
        4. Verify LLMResponse is created with custom model ID
        
        Edge cases tested:
        - Custom model ID is used
        - Manual completion text is captured
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to manual mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.MANUAL:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        # Enter manual completion
        frame.completion_area.setPlainText("Manually entered completion")
        frame.manual_model_id_edit.setText("gpt-4")
        frame.generate_completion()
        qt_app.processEvents()

        assert frame.generated_completion is not None
        assert frame.generated_completion.model_id == "gpt-4"
        assert frame.generated_completion.completion_text == "Manually entered completion"
        assert frame.save_btn.isEnabled()

    def test_manual_completion_default_model_id(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                ensure_google_icon_font: None) -> None:
        """
        Manual mode uses default model ID when field is empty.
        
        Flow:
        1. Switch to manual mode
        2. Enter completion text but leave model ID empty
        3. Trigger save
        4. Verify default model ID "manual" is used
        
        Edge cases tested:
        - Empty model ID defaults to "manual"
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to manual mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.MANUAL:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        # Enter manual completion with empty model ID
        frame.completion_area.setPlainText("Manual completion")
        frame.manual_model_id_edit.clear()
        frame.generate_completion()
        qt_app.processEvents()

        assert frame.generated_completion is not None
        assert frame.generated_completion.model_id == "manual"


class TestNewCompletionFrameTokenByTokenMode:
    """
    Test token-by-token generation mode.
    """

    def test_token_by_token_fetch_candidates(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                             ensure_google_icon_font: None) -> None:
        """
        Token-by-token mode fetches token candidates successfully.
        
        Flow:
        1. Switch to TOKEN_BY_TOKEN mode
        2. Mock controller and token logprobs
        3. Trigger next token fetch
        4. Verify token picker is populated
        
        Edge cases tested:
        - Controller is created
        - Token picker widget is set with candidates
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.TOKEN_BY_TOKEN:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        # Mock controller and token fetch
        mock_controller = MagicMock()
        mock_tokens = SinglePositionTopLogprobs([
            create_test_single_position_token("Hello", -0.1),
            create_test_single_position_token(" world", -0.5),
            create_test_single_position_token(" there", -0.8),
        ])
        mock_controller.fetch_next_token_logprobs_for_prefix.return_value = mock_tokens

        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.generate_completion()
            qt_app.processEvents()

        # Token picker widget should be set (not just visible, but populated)
        assert frame.token_picker_area.widget() is not None

    def test_token_by_token_selection_appends_to_prefix(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                        temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Selecting a token in token-by-token mode appends to prefix.
        
        Flow:
        1. Switch to TOKEN_BY_TOKEN mode
        2. Fetch token candidates
        3. Select a token
        4. Verify prefix is updated
        5. Verify continue button state is updated
        
        Edge cases tested:
        - Token selection updates prefix
        - UI state is updated correctly
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.TOKEN_BY_TOKEN:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        # Simulate token selection
        test_token = create_test_single_position_token("Hello", -0.1)
        frame._on_token_selected([test_token])
        qt_app.processEvents()

        assert frame.token_by_token_prefix == "Hello"
        assert len(frame.token_by_token_tokens) == 1
        assert frame.token_by_token_tokens[0].token_str == "Hello"
        # Continue button should be enabled after token selection
        assert frame.continue_generation_btn.isEnabled() or frame.continue_generation_btn.isVisible()

    def test_token_by_token_multiple_selections(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Multiple token selections build up prefix correctly.
        
        Flow:
        1. Switch to TOKEN_BY_TOKEN mode
        2. Select first token
        3. Select second token
        4. Verify both tokens are in prefix
        
        Edge cases tested:
        - Multiple selections accumulate correctly
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        for i in range(frame.mode_combo.count()):
            if frame.mode_combo.itemData(i) == CompletionMode.TOKEN_BY_TOKEN:
                frame.mode_combo.setCurrentIndex(i)
                break

        qt_app.processEvents()

        # Simulate multiple token selections
        token1 = create_test_single_position_token("Hello", -0.1)
        token2 = create_test_single_position_token(" world", -0.5)

        frame._on_token_selected([token1])
        qt_app.processEvents()
        frame._on_token_selected([token2])
        qt_app.processEvents()

        assert frame.token_by_token_prefix == "Hello world"
        assert len(frame.token_by_token_tokens) == 2


class TestNewCompletionFrameContinuationMode:
    """
    Test continuation mode for truncated completions.
    """

    def test_set_completion_for_continuation(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                            ensure_google_icon_font: None) -> None:
        """
        set_completion_for_continuation sets up continuation mode correctly.
        
        Flow:
        1. Create a completion
        2. Call set_completion_for_continuation
        3. Verify mode switches to CONTINUATION
        4. Verify completion is displayed
        
        Edge cases tested:
        - Mode is automatically switched
        - Completion text is displayed
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Create a sample completion
        _, completion = build_sample_with_completion(temp_dataset)

        # Set for continuation
        frame.set_completion_for_continuation(completion)
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.CONTINUATION
        assert frame.current_completion == completion
        assert completion.completion_text in frame.completion_area.toPlainText()

    def test_continuation_mode_generates_continuation(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                     temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Continuation mode generates continuation of truncated completion.
        
        Flow:
        1. Set up continuation mode with a completion
        2. Mock controller to return continuation
        3. Trigger continuation generation
        4. Verify continuation is generated
        
        Edge cases tested:
        - Controller generate_continuation is called
        - Result is displayed
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Create a sample completion
        _, completion = build_sample_with_completion(temp_dataset)
        completion.is_truncated = True

        # Set for continuation
        frame.set_completion_for_continuation(completion)
        qt_app.processEvents()

        # Mock controller
        mock_controller = MagicMock()
        mock_continuation = create_test_llm_response(
            model_id="mock-echo-model",
            completion_text="Original text... continued text here",
            prefill=None,
        )
        mock_controller.generate_continuation.return_value = mock_continuation

        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.generate_completion()
            qt_app.processEvents()

        assert frame.generated_completion is not None
        assert "continued text" in frame.generated_completion.completion_text


class TestNewCompletionFrameSaveCompletion:
    """
    Test save completion functionality.
    """

    def test_save_completion_emits_signal(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                         ensure_google_icon_font: None) -> None:
        """
        Saving completion emits completion_accepted signal.
        
        Flow:
        1. Generate a completion
        2. Connect to completion_accepted signal
        3. Trigger save
        4. Verify signal is emitted with completion
        
        Edge cases tested:
        - Signal emission works correctly
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Create a mock completion
        test_completion = create_test_llm_response()
        frame.generated_completion = test_completion

        # Connect signal
        signal_received = []

        def on_completion_accepted(completion):
            signal_received.append(completion)

        frame.completion_accepted.connect(on_completion_accepted)

        # Trigger save
        frame.save_completion()
        qt_app.processEvents()

        assert len(signal_received) == 1
        # The signal should contain the completion that was saved
        assert signal_received[0] == test_completion

    def test_save_completion_resets_state(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                         ensure_google_icon_font: None) -> None:
        """
        Saving completion resets widget state.
        
        Flow:
        1. Generate a completion
        2. Save completion
        3. Verify state is reset
        
        Edge cases tested:
        - Generated completion is cleared
        - Mode is reset to REGULAR
        - Token-by-token state is cleared
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Set up token-by-token state
        frame.token_by_token_prefix = "test"
        frame.token_by_token_tokens = [create_test_single_position_token("test", -0.1)]
        frame.generated_completion = create_test_llm_response()

        # Save
        frame.save_completion()
        qt_app.processEvents()

        assert frame.generated_completion is None
        assert frame.token_by_token_prefix == ""
        assert not frame.token_by_token_tokens
        assert frame.current_mode == CompletionMode.REGULAR
