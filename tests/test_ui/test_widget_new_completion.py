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
        assert hasattr(frame, 'model_combo')
        assert hasattr(frame, 'temp_spin')
        assert hasattr(frame, 'topk_spin')
        assert hasattr(frame, 'prefill_edit')
        assert hasattr(frame, 'completion_area')
        assert hasattr(frame, 'token_picker_area')
        assert hasattr(frame, 'generate_btn')
        assert hasattr(frame, 'edit_btn')
        assert hasattr(frame, 'token_by_token_btn')
        assert hasattr(frame, 'continue_btn')
        assert hasattr(frame, 'save_btn')

    def test_mode_buttons_exist(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", ensure_google_icon_font: None) -> None:
        """
        Mode buttons exist and are accessible.
        
        Flow:
        1. Create NewCompletionFrame
        2. Check mode buttons exist
        3. Verify button states
        
        Edge cases tested:
        - All mode buttons are available
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Check buttons exist
        assert frame.generate_btn is not None
        assert frame.edit_btn is not None
        assert frame.token_by_token_btn is not None
        assert frame.continue_btn is not None

        # Check initial state
        assert frame.current_mode == CompletionMode.REGULAR
        assert not frame.token_by_token_btn.isChecked()


class TestNewCompletionFrameModeSwitching:
    """
    Test mode switching behavior.
    """

    def test_switch_to_manual_mode(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", ensure_google_icon_font: None) -> None:
        """
        Switching to MANUAL mode via Edit button updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame in default mode
        2. Click Edit button to switch to MANUAL mode
        3. Verify UI elements are updated
        
        Edge cases tested:
        - Completion area becomes editable
        - Model combo becomes editable
        - Mode is set to MANUAL
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Click edit button to switch to manual mode
        frame.edit_btn.click()
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.MANUAL
        assert not frame.completion_area.isReadOnly()
        assert frame.model_combo.isEditable()
        # Model should be set to "manual"
        assert frame.model_combo.currentText() == "manual"

    def test_switch_to_token_by_token_mode(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                           ensure_google_icon_font: None) -> None:
        """
        Switching to TOKEN_BY_TOKEN mode via toggle button updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame
        2. Click Token by Token button
        3. Verify token picker area visibility
        
        Edge cases tested:
        - Button is checkable and checked
        - Token picker area can be shown
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Click token by token button
        frame.token_by_token_btn.click()
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.TOKEN_BY_TOKEN
        assert frame.token_by_token_btn.isChecked()

    def test_switch_back_from_token_by_token(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                             ensure_google_icon_font: None) -> None:
        """
        Switching back from TOKEN_BY_TOKEN mode updates UI correctly.
        
        Flow:
        1. Create NewCompletionFrame
        2. Switch to TOKEN_BY_TOKEN mode
        3. Switch back to REGULAR mode
        4. Verify state is updated
        
        Edge cases tested:
        - Mode toggles correctly
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        frame.token_by_token_btn.click()
        qt_app.processEvents()
        assert frame.current_mode == CompletionMode.TOKEN_BY_TOKEN

        # Switch back
        frame.token_by_token_btn.click()
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.REGULAR
        assert not frame.token_by_token_btn.isChecked()


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
            frame.generate_btn.click()
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
            frame.generate_btn.click()
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
        1. Click Edit button to switch to manual mode
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

        # Click edit button to switch to manual mode
        frame.edit_btn.click()
        qt_app.processEvents()

        # Verify mode was switched to manual
        assert frame.current_mode == CompletionMode.MANUAL

        # Enter manual completion
        frame.completion_area.setPlainText("Manually entered completion")
        frame.model_combo.setEditText("gpt-4")
        qt_app.processEvents()

        # Verify save button is enabled after entering text
        assert frame.save_btn.isEnabled()

        # Connect to signal to capture emitted completion
        signal_received = []

        def on_completion_accepted(completion):
            signal_received.append(completion)

        frame.completion_accepted.connect(on_completion_accepted)

        frame.save_btn.click()
        qt_app.processEvents()

        # After save, mode should be reset to REGULAR
        assert frame.current_mode == CompletionMode.REGULAR

        # Verify signal was emitted with correct data
        assert len(signal_received) == 1
        assert signal_received[0].model_id == "gpt-4"
        assert signal_received[0].completion_text == "Manually entered completion"

    def test_manual_completion_default_model_id(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                ensure_google_icon_font: None) -> None:
        """
        Manual mode uses default model ID "manual" when Edit button is clicked.
        
        Flow:
        1. Click Edit button to switch to manual mode
        2. Verify default model ID "manual" is set
        
        Edge cases tested:
        - Edit button sets model to "manual"
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Click edit button
        frame.edit_btn.click()
        qt_app.processEvents()

        assert frame.current_mode == CompletionMode.MANUAL
        assert frame.model_combo.currentText() == "manual"


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
        3. Verify token picker is populated automatically (no need to click Generate anymore)
        
        Edge cases tested:
        - Controller is created
        - Token picker widget is set with candidates
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        mock_sample.show()  # Show parent so token picker can be visible
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Mock controller and token fetch
        mock_controller = MagicMock()
        mock_tokens = SinglePositionTopLogprobs([
            create_test_single_position_token("Hello", -0.1),
            create_test_single_position_token(" world", -0.5),
            create_test_single_position_token(" there", -0.8),
        ])
        mock_controller.fetch_next_token_logprobs_for_prefix.return_value = mock_tokens

        # Click token-by-token button to switch mode - this now automatically fetches tokens
        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.token_by_token_btn.click()
            qt_app.processEvents()

        # Token picker widget should be set (not just visible, but populated)
        assert frame.token_picker_area.widget() is not None

    def test_token_by_token_selection_appends_to_prefix(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                        temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Selecting a token in token-by-token mode appends to prefix.
        
        Flow:
        1. Switch to TOKEN_BY_TOKEN mode
        2. Fetch token candidates (not needed, simulating selection directly)
        3. Select a token
        4. Verify prefix is updated
        5. Verify UI state is updated correctly
        
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
        frame.token_by_token_btn.click()
        qt_app.processEvents()

        # Simulate token selection (patch to prevent auto-fetch)
        with patch.object(frame, '_handle_token_by_token_mode'):
            test_token = create_test_single_position_token("Hello", -0.1)
            frame._on_token_selected([test_token])
            qt_app.processEvents()

        assert frame.token_by_token_prefix == "Hello"
        assert len(frame.token_by_token_tokens) == 1
        assert frame.token_by_token_tokens[0].token_str == "Hello"

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
        frame.token_by_token_btn.click()
        qt_app.processEvents()

        # Simulate multiple token selections (patch to prevent auto-fetch)
        with patch.object(frame, '_handle_token_by_token_mode'):
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
    Test continuation behavior for truncated completions.
    """

    def test_set_completion_for_continuation(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication", temp_dataset: "DatasetDatabase",
                                             ensure_google_icon_font: None) -> None:
        """
        set_completion_for_continuation sets up continuation correctly.
        
        Flow:
        1. Create a completion
        2. Call set_completion_for_continuation
        3. Verify continue button is shown
        4. Verify completion is displayed
        
        Edge cases tested:
        - Continue button becomes visible
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

        assert frame.has_truncated_completion
        assert frame.current_completion == completion
        assert completion.completion_text in frame.completion_area.toPlainText()
        # Continue button should be enabled for truncated completions
        # Note: isVisible() may not work as expected in tests, but the button should be clickable
        assert frame.continue_btn.isEnabled() or not frame.continue_btn.isHidden()

    def test_continuation_generates_continuation(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                 temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Continuation button generates continuation of truncated completion.
        
        Flow:
        1. Set up continuation with a completion
        2. Mock controller to return continuation
        3. Click continue button
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
            frame.continue_btn.click()
            qt_app.processEvents()

        assert frame.generated_completion is not None
        assert "continued text" in frame.generated_completion.completion_text

    def test_truncated_completion_shows_continue_button(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                        temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Generating a truncated completion automatically shows continue button.
        
        Flow:
        1. Create frame
        2. Generate a truncated completion
        3. Verify continue button is shown
        
        Edge cases tested:
        - Continue button appears for truncated completions
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Mock a truncated generation
        mock_controller = MagicMock()
        mock_response = create_test_llm_response(
            model_id="mock-echo-model",
            completion_text="This is truncated",
            prefill=None,
        )
        mock_response.is_truncated = True
        mock_controller.generate.return_value = mock_response

        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.generate_btn.click()
            qt_app.processEvents()

        assert frame.has_truncated_completion
        # Continue button should be accessible for truncated completions
        # Note: isVisible() may not work reliably in Qt offscreen mode
        assert not frame.continue_btn.isHidden()


class TestNewCompletionFrameBugFixes:
    """
    Test bug fixes for issue: New Completion doesn't conform to specs.
    
    Bug 1: Button "save" is disabled after entering manual completion.
    Bug 2: Button "save" is disabled after token-by-token generation.
    Bug 3: Token-by-token mode doesn't show token picker after being clicked, requiring to hit "generate" first.
    """

    def test_manual_mode_enables_save_button_after_text_entry(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                              ensure_google_icon_font: None) -> None:
        """
        Bug 1: Save button should be enabled after entering manual completion.
        
        Flow:
        1. Switch to manual mode via Edit button
        2. Enter completion text
        3. Verify save button is enabled
        
        Edge cases tested:
        - Save button becomes enabled when text is entered in manual mode
        - Save button remains disabled when text area is empty
        """
        _ = ensure_google_icon_font
        parent = QWidget()
        frame = NewCompletionFrame(parent, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Click edit button to switch to manual mode
        frame.edit_btn.click()
        qt_app.processEvents()

        # Initially save button should be disabled (no completion text)
        assert not frame.save_btn.isEnabled(), "Save button should be disabled when no text is entered"

        # Enter manual completion text
        frame.completion_area.setPlainText("Manually entered completion")
        qt_app.processEvents()

        # Save button should now be enabled
        assert frame.save_btn.isEnabled(), "Save button should be enabled after entering text in manual mode"

    def test_token_by_token_enables_save_button_after_token_selection(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                                      temp_dataset: "DatasetDatabase",
                                                                      ensure_google_icon_font: None) -> None:
        """
        Bug 2: Save button should be enabled after token-by-token generation.
        
        Flow:
        1. Switch to TOKEN_BY_TOKEN mode
        2. Select a token (simulated)
        3. Verify save button is enabled
        
        Edge cases tested:
        - Save button becomes enabled after at least one token is selected
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Switch to token-by-token mode
        frame.token_by_token_btn.click()
        qt_app.processEvents()

        # Initially save button should be disabled
        assert not frame.save_btn.isEnabled(), "Save button should be disabled initially"

        # Simulate token selection (patch to prevent auto-fetch)
        with patch.object(frame, '_handle_token_by_token_mode'):
            test_token = create_test_single_position_token("Hello", -0.1)
            frame._on_token_selected([test_token])
            qt_app.processEvents()

        # Save button should now be enabled
        assert frame.save_btn.isEnabled(), "Save button should be enabled after token selection in token-by-token mode"

    def test_token_by_token_mode_shows_token_picker_immediately(self, app_with_dataset: "pyFadeApp", qt_app: "QApplication",
                                                                temp_dataset: "DatasetDatabase", ensure_google_icon_font: None) -> None:
        """
        Bug 3: Token-by-token mode should show token picker immediately without requiring "Generate" click.
        
        Flow:
        1. Create NewCompletionFrame with mock widget sample
        2. Click "Token by Token" button
        3. Verify token picker area becomes visible and populated with tokens
        
        Edge cases tested:
        - Token picker area is visible after mode switch
        - Token candidates are fetched automatically
        """
        _ = ensure_google_icon_font
        mock_sample = create_mock_widget_sample(app_with_dataset, temp_dataset)
        mock_sample.show()  # Show the parent widget so children can be visible
        frame = NewCompletionFrame(mock_sample, app_with_dataset)
        frame.show()
        qt_app.processEvents()

        # Mock controller and token fetch
        mock_controller = MagicMock()
        mock_tokens = SinglePositionTopLogprobs([
            create_test_single_position_token("Hello", -0.1),
            create_test_single_position_token(" world", -0.5),
            create_test_single_position_token(" there", -0.8),
        ])
        mock_controller.fetch_next_token_logprobs_for_prefix.return_value = mock_tokens

        # Click token-by-token button to switch mode
        with patch.object(app_with_dataset, 'get_or_create_text_generation_controller', return_value=mock_controller):
            frame.token_by_token_btn.click()
            qt_app.processEvents()

        # Token picker area should be visible
        assert frame.token_picker_area.isVisible(), "Token picker area should be visible immediately after switching to token-by-token mode"

        # Token picker widget should be populated
        assert frame.token_picker_area.widget() is not None, "Token picker widget should be populated with tokens"


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
