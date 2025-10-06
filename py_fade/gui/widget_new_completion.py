"""Widget for configuring and launching new completion generations."""

import logging
from enum import Enum
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_fade.data_formats.base_data_classes import SinglePositionToken
from py_fade.gui.components.widget_token_picker import WidgetTokenPicker
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.controllers.text_generation_controller import TextGenerationController
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.providers.llm_response import LLMResponse


class CompletionMode(Enum):
    """
    Enum for different completion generation modes.
    """
    REGULAR = "regular"  # Regular generation from prompt + optional prefill
    MANUAL = "manual"  # Manual completion input
    TOKEN_BY_TOKEN = "token_by_token"  # Token by token generation with token picker


class NewCompletionFrame(QFrame):
    """
    UI frame for creating a new completion with multiple modes.

    Supports three modes:
    - REGULAR: Regular generation from prompt + optional prefill
    - MANUAL: Manual completion input with optional model ID
    - TOKEN_BY_TOKEN: Token by token generation with token picker

    Has model picker (combobox), temperature, top_k controls,
    prefill/completion text areas, and mode-specific controls.
    Continuation is automatically available via button when completion is truncated.
    """

    completion_accepted = pyqtSignal(object)  # Signal emitted when completion is accepted and should be saved
    app: "pyFadeApp"
    log: logging.Logger
    current_mode: CompletionMode
    generated_completion: "LLMResponse | None"
    current_completion: "PromptCompletion | None"  # For continuation tracking
    token_by_token_controller: "TextGenerationController | None"
    token_by_token_prefix: str  # Current token-by-token prefix
    token_by_token_tokens: list[SinglePositionToken]  # Selected tokens for token-by-token
    has_truncated_completion: bool  # Track if current completion is truncated for continuation button

    def __init__(self, parent: QWidget, app: "pyFadeApp"):
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.generated_completion = None
        self.current_completion = None
        self.current_mode = CompletionMode.REGULAR
        self.token_by_token_controller = None
        self.token_by_token_prefix = ""
        self.token_by_token_tokens = []
        self.has_truncated_completion = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # self.setStyleSheet("background-color: #f0f8ff; border: 2px dashed #4169e1;")

        self.setup_ui()

    def setup_ui(self):
        """Construct all controls composing the new completion frame."""

        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Generate New Completion")
        header_layout.addWidget(header)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Model picker (editable for manual mode)
        controls_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.addItems(self.app.available_models)
        controls_layout.addWidget(self.model_combo)

        # Temperature
        controls_layout.addWidget(QLabel("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.app.providers_manager.default_temperature)
        controls_layout.addWidget(self.temp_spin)

        # Top-k
        controls_layout.addWidget(QLabel("Top-k:"))
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 100)
        self.topk_spin.setValue(self.app.providers_manager.default_top_k)
        controls_layout.addWidget(self.topk_spin)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Prefill text area
        layout.addWidget(QLabel("Prefill (optional):"))
        self.prefill_edit = QPlainTextEdit()
        self.prefill_edit.setPlaceholderText("Enter prefill text here...")
        self.prefill_edit.setMaximumHeight(80)
        layout.addWidget(self.prefill_edit)

        # Main content area with completion and token picker
        # This will be horizontal layout for token-by-token mode
        self.content_layout = QHBoxLayout()

        # Completion area container
        self.completion_container = QWidget()
        completion_container_layout = QVBoxLayout(self.completion_container)
        completion_container_layout.setContentsMargins(0, 0, 0, 0)

        self.completion_area = QTextEdit()
        self.completion_area.setReadOnly(True)
        self.completion_area.setMinimumHeight(120)
        self.completion_area.setPlaceholderText("Generated completion text...")
        # Connect text changed signal to update save button state in manual mode
        self.completion_area.textChanged.connect(self._on_completion_text_changed)
        completion_container_layout.addWidget(self.completion_area)

        self.content_layout.addWidget(self.completion_container)

        # Token picker area (for token-by-token mode, shown to the right)
        self.token_picker_area = QScrollArea()
        self.token_picker_area.setWidgetResizable(True)
        self.token_picker_area.setVisible(False)  # Hidden by default
        self.token_picker_area.setMinimumHeight(200)
        self.token_picker_area.setMinimumWidth(300)
        self.content_layout.addWidget(self.token_picker_area)

        layout.addLayout(self.content_layout)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        self.generate_btn = QPushButtonWithIcon("send", parent=self, icon_size=20, button_size=36)
        self.generate_btn.setToolTip("Generate completion with current parameters")
        self.generate_btn.clicked.connect(self._handle_generate)
        buttons_layout.addWidget(self.generate_btn)

        self.edit_btn = QPushButtonWithIcon("edit", parent=self, icon_size=20, button_size=36)
        self.edit_btn.setToolTip("Switch to manual editing mode")
        self.edit_btn.clicked.connect(self._handle_edit)
        buttons_layout.addWidget(self.edit_btn)

        self.token_by_token_btn = QPushButtonWithIcon("step", parent=self, icon_size=20, button_size=36)
        self.token_by_token_btn.setToolTip("Token by token generation mode")
        self.token_by_token_btn.setCheckable(True)
        self.token_by_token_btn.clicked.connect(self._handle_token_by_token_toggle)
        buttons_layout.addWidget(self.token_by_token_btn)

        self.continue_btn = QPushButtonWithIcon("resume", parent=self, icon_size=20, button_size=36)
        self.continue_btn.setToolTip("Continue truncated completion")
        self.continue_btn.clicked.connect(self._handle_continuation)
        self.continue_btn.setVisible(False)
        buttons_layout.addWidget(self.continue_btn)

        self.save_btn = QPushButtonWithIcon("check", parent=self, icon_size=20, button_size=36)
        self.save_btn.setToolTip("Save completion to dataset")
        self.save_btn.clicked.connect(self.save_completion)
        self.save_btn.setEnabled(False)
        buttons_layout.addWidget(self.save_btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # Status label
        self.status_label = QLabel("")
        # self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Initialize UI state
        self._update_ui_for_mode()

    def _handle_generate(self):
        """
        Handle Generate button click.
        
        Generates completion based on current mode (regular or token-by-token).
        """
        if not self.app:
            self.status_label.setText("Error: No app provider available")
            return

        if self.current_mode == CompletionMode.TOKEN_BY_TOKEN:
            self._handle_token_by_token_mode()
        else:
            self._handle_regular_mode()

    def _on_completion_text_changed(self) -> None:
        """
        Handle completion area text changed event.
        
        Updates save button state in manual mode based on text content.
        """
        if self.current_mode == CompletionMode.MANUAL:
            # Enable save button if there's any non-empty text in manual mode
            has_text = bool(self.completion_area.toPlainText().strip())
            self.save_btn.setEnabled(has_text)

    def _handle_edit(self):
        """
        Handle Edit button click.
        
        Switches to manual mode, keeping any generated text editable.
        """
        self.current_mode = CompletionMode.MANUAL
        # Update UI will handle setting model combo to editable and "manual"
        self._update_ui_for_mode()
        self.log.debug("Switched to manual edit mode")

    def _handle_token_by_token_toggle(self, checked: bool):
        """
        Handle Token by Token button toggle.
        
        Switches between regular and token-by-token modes.
        """
        if checked:
            # Switching to token-by-token mode
            self.current_mode = CompletionMode.TOKEN_BY_TOKEN
            # Validate model - if it's "manual" or invalid, switch to first available model
            current_model = self.model_combo.currentText()
            if current_model not in self.app.available_models:
                if self.app.available_models:
                    self.model_combo.setCurrentIndex(0)
                    self.log.debug("Invalid model for token-by-token, switched to %s", self.model_combo.currentText())
        else:
            # Switching back to regular mode
            self.current_mode = CompletionMode.REGULAR

        self._update_ui_for_mode()
        self.log.debug("Mode changed to %s", self.current_mode)

        # Automatically fetch token candidates when switching to token-by-token mode
        if checked:
            self._handle_token_by_token_mode()

    def _handle_continuation(self):
        """
        Handle Continue button click.
        
        Continues generation from truncated completion in current mode.
        """
        if not self.current_completion:
            self.status_label.setText("Error: No completion to continue")
            return

        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, "prompt_area"):
            widget_sample = widget_sample.parent()

        if not widget_sample:
            self.status_label.setText("Error: Cannot find widget sample")
            return

        self.continue_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating continuation...")
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore # Force UI update

        # Get mapped model from current completion
        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model '{self.model_combo.currentText()}' not found")
            self.continue_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)
            return

        prompt_text: str = widget_sample.prompt_area.toPlainText().strip()  # type: ignore
        context_length: int = widget_sample.context_length_field.value()  # type: ignore
        max_tokens: int = widget_sample.max_tokens_field.value()  # type: ignore

        try:
            controller = self.app.get_or_create_text_generation_controller(mapped_model, prompt_text, context_length=context_length,
                                                                           max_tokens=max_tokens)
        except ValueError as e:
            self.status_label.setText(f"Error: {e}")
            self.continue_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)
            return

        # Generate continuation
        try:
            self.generated_completion = controller.generate_continuation(
                original_completion=self.current_completion,
                context_length=context_length,
                max_tokens=max_tokens,
            )
            if self.generated_completion:
                self.display_completion()
            else:
                self.status_label.setText("Error: Continuation generation failed")
                self.continue_btn.setEnabled(True)
                self.generate_btn.setEnabled(True)
        except (RuntimeError, ValueError) as e:
            self.status_label.setText(f"Error: {e}")
            self.continue_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)

    def _update_ui_for_mode(self) -> None:
        """
        Update UI elements visibility and state based on current mode.
        """
        is_manual = self.current_mode == CompletionMode.MANUAL
        is_token_by_token = self.current_mode == CompletionMode.TOKEN_BY_TOKEN

        # Completion area behavior
        if is_manual:
            self.completion_area.setReadOnly(False)
            self.completion_area.setPlaceholderText("Enter completion text manually...")
            # Make model combo editable in manual mode and set to "manual"
            self.model_combo.setEditable(True)
            self.model_combo.setEditText("manual")
        else:
            self.completion_area.setReadOnly(True)
            self.completion_area.setPlaceholderText("Generated completion text...")
            self.model_combo.setEditable(False)

        # Token picker visibility and layout
        if is_token_by_token:
            self.token_picker_area.setVisible(True)
            self.token_picker_area.show()  # Explicitly show as well
            # Adjust content layout stretch for side-by-side view
            # Give token picker area 2x more space than completion area
            self.content_layout.setStretch(0, 1)  # Completion area
            self.content_layout.setStretch(1, 2)  # Token picker area - 2x wider
        else:
            self.token_picker_area.setVisible(False)
            self.token_picker_area.hide()
            self.content_layout.setStretch(0, 1)
            self.content_layout.setStretch(1, 0)

        # Update button states
        self.token_by_token_btn.setChecked(is_token_by_token)

        # Continue button visibility based on truncation
        if self.has_truncated_completion:
            self.continue_btn.setVisible(True)
            self.continue_btn.show()
        else:
            self.continue_btn.setVisible(False)
            self.continue_btn.hide()

        # Update status label
        if is_manual:
            self.status_label.setText("Manual mode: Enter completion text, edit model ID if needed, then save.")
        elif is_token_by_token:
            self.status_label.setText("Token-by-token mode: Click 'Generate' to see token candidates.")
        else:
            self.status_label.setText("")

    def _handle_regular_mode(self) -> None:
        """Handle regular generation mode."""
        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, "prompt_area"):
            widget_sample = widget_sample.parent()

        if not widget_sample:
            self.status_label.setText("Error: Cannot find prompt area")
            self.generate_btn.setEnabled(True)
            return

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating...")
        self.completion_area.show()
        self.completion_area.clear()
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore # Force UI update

        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model '{self.model_combo.currentText()}' not found")
            self.generate_btn.setEnabled(True)
            return
        prompt_text: str = widget_sample.prompt_area.toPlainText().strip()  # type: ignore
        context_length: int = widget_sample.context_length_field.value()  # type: ignore
        max_tokens: int = widget_sample.max_tokens_field.value()  # type: ignore
        try:
            controller = self.app.get_or_create_text_generation_controller(mapped_model, prompt_text, context_length=context_length,
                                                                           max_tokens=max_tokens)
        except ValueError as e:
            self.status_label.setText(f"Error: {e}")
            self.generate_btn.setEnabled(True)
            return
        prefill = self.prefill_edit.toPlainText().strip()

        self.generated_completion = controller.generate(
            prefill=prefill,
            temperature=self.temp_spin.value(),
            top_k=self.topk_spin.value(),
            context_length=context_length,
            max_tokens=max_tokens,
        )
        self.display_completion()

    def _handle_token_by_token_mode(self) -> None:
        """Handle token-by-token generation mode."""
        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, "prompt_area"):
            widget_sample = widget_sample.parent()

        if not widget_sample:
            self.status_label.setText("Error: Cannot find prompt area")
            return

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Fetching token candidates...")
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore # Force UI update

        # Get or create controller - validate model first
        current_model_text = self.model_combo.currentText()
        if current_model_text not in self.app.available_models:
            # Invalid model, switch to first available
            if self.app.available_models:
                self.model_combo.setCurrentIndex(0)
                current_model_text = self.model_combo.currentText()
                self.log.debug("Invalid model for token-by-token, switched to %s", current_model_text)
            else:
                self.status_label.setText("Error: No available models")
                self.generate_btn.setEnabled(True)
                return

        mapped_model = self.app.providers_manager.get_mapped_model(current_model_text)
        if not mapped_model:
            self.status_label.setText(f"Error: Model '{current_model_text}' not found")
            self.generate_btn.setEnabled(True)
            return

        prompt_text: str = widget_sample.prompt_area.toPlainText().strip()  # type: ignore
        context_length: int = widget_sample.context_length_field.value()  # type: ignore
        max_tokens: int = widget_sample.max_tokens_field.value()  # type: ignore

        try:
            if not self.token_by_token_controller:
                self.token_by_token_controller = self.app.get_or_create_text_generation_controller(
                    mapped_model, prompt_text, context_length=context_length, max_tokens=max_tokens)

            # Get current prefix - can come from prefill, manual input, or accumulated tokens
            # Support manual input in completion area
            manual_text = self.completion_area.toPlainText().strip()
            prefill_text = self.prefill_edit.toPlainText().strip()

            if manual_text and not self.token_by_token_prefix:
                # User has entered manual text, use it as starting point
                current_prefix = manual_text
            else:
                # Use prefill + accumulated tokens
                current_prefix = prefill_text + self.token_by_token_prefix

            # Fetch next token candidates
            token_logprobs = self.token_by_token_controller.fetch_next_token_logprobs_for_prefix(current_prefix, 100)

            # Display token picker
            self._show_token_picker(token_logprobs)

        except (RuntimeError, ValueError) as e:
            self.status_label.setText(f"Error: {e}")
            self.generate_btn.setEnabled(True)

    def _show_token_picker(self, token_logprobs) -> None:
        """Show token picker widget with given tokens."""
        # Create token picker widget
        token_picker = WidgetTokenPicker(
            self.token_picker_area,
            token_logprobs,
            multi_select=False,  # Single select for token-by-token
        )

        # Connect token selection signal
        token_picker.tokens_selected.connect(self._on_token_selected)

        # Set as widget for scroll area
        self.token_picker_area.setWidget(token_picker)
        self.token_picker_area.setVisible(True)

        self.status_label.setText("Select a token to continue...")
        self.generate_btn.setEnabled(True)

    def _on_token_selected(self, selected_tokens: list[SinglePositionToken]) -> None:
        """
        Handle token selection in token-by-token mode.
        
        Appends selected token to current prefix, updates display, and automatically fetches next tokens.
        """
        if not selected_tokens:
            return

        token = selected_tokens[0]  # Single select mode
        self.log.info("Token selected: %s", token.token_str)

        # Append to prefix
        self.token_by_token_prefix += token.token_str
        self.token_by_token_tokens.append(token)

        # Update completion display
        self.completion_area.setPlainText(self.prefill_edit.toPlainText().strip() + self.token_by_token_prefix)
        self.completion_area.show()

        # Enable save button after at least one token is selected
        self.save_btn.setEnabled(True)

        # Automatically fetch next tokens
        self.status_label.setText(f"Token added: '{token.token_str}'. Fetching next candidates...")
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore

        # Fetch next token candidates automatically
        self._handle_token_by_token_mode()

    def continue_from_token_by_token(self) -> None:
        """
        Continue regular generation from current token-by-token sequence.
        
        Uses the accumulated prefix as a high-fidelity prefill.
        This is called when user clicks Continue button in token-by-token mode.
        """
        if not self.token_by_token_controller or not self.token_by_token_tokens:
            self.status_label.setText("Error: No token-by-token sequence to continue from")
            return

        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, "prompt_area"):
            widget_sample = widget_sample.parent()

        if not widget_sample:
            self.status_label.setText("Error: Cannot find widget sample")
            return

        self.continue_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.status_label.setText("Continuing generation...")
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore # Force UI update

        context_length: int = widget_sample.context_length_field.value()  # type: ignore
        max_tokens: int = widget_sample.max_tokens_field.value()  # type: ignore

        try:
            # Use the accumulated tokens as prefill
            # Import here to avoid circular imports
            from py_fade.data_formats.base_data_classes import CompletionPrefill, CompletionTokenLogprobs  # pylint: disable=import-outside-toplevel

            prefill_text = self.prefill_edit.toPlainText().strip()
            completion_prefill = CompletionPrefill.from_tokens(CompletionTokenLogprobs(self.token_by_token_tokens))

            # Generate continuation
            response = self.token_by_token_controller.mapped_model.generate(
                prompt=self.token_by_token_controller.prompt_conversation,
                prefill=completion_prefill,
                temperature=self.temp_spin.value(),
                top_k=self.topk_spin.value(),
                context_length=context_length,
                max_tokens=max_tokens,
            )

            # Reconstruct full completion with token-by-token prefix
            self.token_by_token_controller.reconstruct_logprobs_and_completion_text(
                response,
                CompletionTokenLogprobs(self.token_by_token_tokens),
                None,
            )

            # Set prefill text to original prefill (if any)
            response.prefill = prefill_text if prefill_text else None

            self.generated_completion = response
            self.display_completion()

        except (RuntimeError, ValueError) as e:
            self.status_label.setText(f"Error: {e}")
            self.continue_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)

    def display_completion(self):
        """Display the generated completion with prefill highlighting."""
        if not self.generated_completion:
            return

        self.completion_area.show()
        self.completion_area.clear()

        cursor = self.completion_area.textCursor()

        # Highlight prefill if present
        if self.generated_completion.prefill:
            # Prefill format - highlighted
            prefill_format = QTextCharFormat()
            prefill_format.setBackground(QColor("#fffacd"))  # Light yellow
            prefill_format.setForeground(QColor("#8b4513"))  # Brown text

            cursor.insertText(self.generated_completion.prefill, prefill_format)

        # Regular completion text
        normal_format = QTextCharFormat()
        cursor.insertText(self.generated_completion.generated_part_text, normal_format)

        # Update UI state
        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        # Check if completion is truncated and update continuation button
        self.has_truncated_completion = self.generated_completion.is_truncated
        # We need to create a proper completion object for continuation, but for now we'll just track the state
        # The calling code (WidgetSample) will call set_completion_for_continuation when needed
        # Update UI to reflect truncation state (which will show/hide continue button)
        self._update_ui_for_mode()

        status_msg = f"Generated by {self.generated_completion.model_id}"
        if self.has_truncated_completion:
            status_msg += " (truncated - click Continue for more)"
        self.status_label.setText(status_msg)

    def save_completion(self):
        """Save the generated completion and emit signal."""
        # Import here to avoid circular imports
        from py_fade.providers.llm_response import LLMResponse  # pylint: disable=import-outside-toplevel

        # For manual mode, always create completion from current text area content
        # This handles both: 1) manual entry from scratch, 2) editing after generation
        if self.current_mode == CompletionMode.MANUAL:
            model_id = self.model_combo.currentText() or "manual"
            completion_text = self.completion_area.toPlainText().strip()
            if not completion_text:
                self.status_label.setText("Error: No completion text entered")
                return

            self.generated_completion = LLMResponse(
                model_id=model_id,
                prompt_conversation=None,  # Will be set when saved
                prefill=None,
                completion_text=completion_text,
                generated_part_text=completion_text,
                temperature=self.temp_spin.value(),
                top_k=self.topk_spin.value(),
                context_length=0,
                max_tokens=0,
                is_truncated=False,
                logprobs=None,
            )
        # For token-by-token mode, create completion from accumulated tokens
        elif self.current_mode == CompletionMode.TOKEN_BY_TOKEN:
            if not self.token_by_token_tokens:
                self.status_label.setText("Error: No tokens selected")
                return

            model_id = self.model_combo.currentText()
            prefill_text = self.prefill_edit.toPlainText().strip()
            # Full completion text includes prefill + accumulated tokens
            completion_text = prefill_text + self.token_by_token_prefix

            self.generated_completion = LLMResponse(
                model_id=model_id,
                prompt_conversation=None,  # Will be set when saved
                prefill=prefill_text if prefill_text else None,
                completion_text=completion_text,
                generated_part_text=self.token_by_token_prefix,
                temperature=self.temp_spin.value(),
                top_k=self.topk_spin.value(),
                context_length=0,
                max_tokens=0,
                is_truncated=False,
                logprobs=None,
            )
        # For regular mode, use the generated completion as-is
        elif not self.generated_completion:
            self.status_label.setText("Error: No completion to save")
            return

        self.completion_accepted.emit(self.generated_completion)
        self.status_label.setText("Completion saved!")

        # Reset for next generation (but keep parameters)
        self.generated_completion = None
        self.has_truncated_completion = False
        self.current_completion = None
        self.token_by_token_controller = None
        self.token_by_token_prefix = ""
        self.token_by_token_tokens = []
        self.completion_area.clear()
        self.token_picker_area.setWidget(None)
        self.token_picker_area.setVisible(False)
        self.save_btn.setEnabled(False)
        self.continue_btn.setVisible(False)

        # Reset to regular mode
        self.current_mode = CompletionMode.REGULAR
        self.token_by_token_btn.setChecked(False)
        self.model_combo.setEditable(False)
        self._update_ui_for_mode()

    def set_completion_for_continuation(self, completion: "PromptCompletion") -> None:
        """
        Set a completion to be continued.
        
        This method displays the completion and shows the continuation button.
        """
        self.current_completion = completion
        self.has_truncated_completion = True

        # Display the completion text
        self.completion_area.setPlainText(completion.completion_text)
        self.completion_area.show()

        # Set model to match completion
        mapped_model = self.app.providers_manager.get_mapped_model(completion.model_id)
        if mapped_model:
            self.set_selected_model(mapped_model)

        # Update UI
        self._update_ui_for_mode()
        self.status_label.setText(f"Ready to continue completion (model: {completion.model_id})")

    def set_selected_model(self, mapped_model: MappedModel | None) -> None:
        """Select the provided model in the combo box when available."""
        if not mapped_model:
            return
        index = self.model_combo.findText(mapped_model.path)
        if index < 0:
            return
        self.model_combo.blockSignals(True)
        self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
