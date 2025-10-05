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
    QLineEdit,
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
    CONTINUATION = "continuation"  # Continuation of current generation if truncated
    MANUAL = "manual"  # Manual completion input
    TOKEN_BY_TOKEN = "token_by_token"  # Token by token generation with token picker


class NewCompletionFrame(QFrame):
    """
    UI frame for creating a new completion with multiple modes.

    Supports four modes:
    - REGULAR: Regular generation from prompt + optional prefill
    - CONTINUATION: Continuation of truncated completion
    - MANUAL: Manual completion input with optional model ID
    - TOKEN_BY_TOKEN: Token by token generation with token picker

    Has model picker (combobox), temperature, top_k controls,
    prefill/completion text areas, and mode-specific controls.
    """

    completion_accepted = pyqtSignal(object)  # Signal emitted when completion is accepted and should be saved
    app: "pyFadeApp"
    log: logging.Logger
    current_mode: CompletionMode
    generated_completion: "LLMResponse | None"
    current_completion: "PromptCompletion | None"  # For continuation mode
    token_by_token_controller: "TextGenerationController | None"
    token_by_token_prefix: str  # Current token-by-token prefix
    token_by_token_tokens: list[SinglePositionToken]  # Selected tokens for token-by-token

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
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # self.setStyleSheet("background-color: #f0f8ff; border: 2px dashed #4169e1;")

        self.setup_ui()

    def setup_ui(self):
        """Construct all controls composing the new completion frame."""

        layout = QVBoxLayout(self)

        # Header with mode selector
        header_layout = QHBoxLayout()
        header = QLabel("Generate New Completion")
        header_layout.addWidget(header)

        # Mode selector
        header_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Regular Generation", CompletionMode.REGULAR)
        self.mode_combo.addItem("Continue Truncated", CompletionMode.CONTINUATION)
        self.mode_combo.addItem("Manual Input", CompletionMode.MANUAL)
        self.mode_combo.addItem("Token by Token", CompletionMode.TOKEN_BY_TOKEN)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        header_layout.addWidget(self.mode_combo)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Model picker
        controls_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
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

        # Manual model ID input (for manual mode)
        manual_model_layout = QHBoxLayout()
        manual_model_layout.addWidget(QLabel("Model ID (manual):"))
        self.manual_model_id_edit = QLineEdit()
        self.manual_model_id_edit.setPlaceholderText("Enter model ID for manual completions (default: manual)")
        self.manual_model_id_edit.setText("manual")
        manual_model_layout.addWidget(self.manual_model_id_edit)
        self.manual_model_id_layout = manual_model_layout
        layout.addLayout(manual_model_layout)

        # Prefill text area
        layout.addWidget(QLabel("Prefill (optional):"))
        self.prefill_edit = QPlainTextEdit()
        self.prefill_edit.setPlaceholderText("Enter prefill text here...")
        self.prefill_edit.setMaximumHeight(80)
        layout.addWidget(self.prefill_edit)

        # Generated completion area
        self.completion_area = QTextEdit()
        self.completion_area.setReadOnly(True)
        self.completion_area.setMinimumHeight(120)
        self.completion_area.setPlaceholderText("Generated completion text...")
        layout.addWidget(self.completion_area)

        # Token picker area (for token-by-token mode)
        self.token_picker_area = QScrollArea()
        self.token_picker_area.setWidgetResizable(True)
        self.token_picker_area.setVisible(False)  # Hidden by default; shown in step-by-step mode
        self.token_picker_area.setMinimumHeight(200)
        layout.addWidget(self.token_picker_area)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        self.generate_btn = QPushButtonWithIcon("send", "Generate", parent=self, icon_size=20, button_size=36)
        self.generate_btn.setToolTip("Generate completion with current parameters")
        self.generate_btn.clicked.connect(self.generate_completion)
        buttons_layout.addWidget(self.generate_btn)

        self.continue_generation_btn = QPushButtonWithIcon("resume", "Continue", parent=self, icon_size=20, button_size=36)
        self.continue_generation_btn.setToolTip("Continue regular generation from current token-by-token sequence")
        self.continue_generation_btn.clicked.connect(self.continue_from_token_by_token)
        self.continue_generation_btn.setVisible(False)
        buttons_layout.addWidget(self.continue_generation_btn)

        self.save_btn = QPushButtonWithIcon("check", "Save", parent=self, icon_size=20, button_size=36)
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

    def set_completion_for_continuation(self, completion: "PromptCompletion") -> None:
        """
        Set a completion to be continued.
        
        This method is used when the widget is in CONTINUATION mode.
        """
        self.current_completion = completion
        # Switch to continuation mode
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == CompletionMode.CONTINUATION:
                self.mode_combo.setCurrentIndex(i)
                break
        # Display the completion text
        self.completion_area.setPlainText(completion.completion_text)
        self.completion_area.show()
        self.status_label.setText(f"Ready to continue completion (model: {completion.model_id})")

    def _on_mode_changed(self, index: int) -> None:
        """
        Handle mode change.
        
        Updates UI visibility and state based on selected mode.
        """
        mode_data = self.mode_combo.itemData(index)
        if mode_data:
            self.current_mode = mode_data
            self._update_ui_for_mode()
            self.log.debug("Mode changed to %s", self.current_mode)

    def _update_ui_for_mode(self) -> None:
        """
        Update UI elements visibility and state based on current mode.
        """
        # Hide/show elements based on mode
        is_manual = self.current_mode == CompletionMode.MANUAL
        is_token_by_token = self.current_mode == CompletionMode.TOKEN_BY_TOKEN
        is_continuation = self.current_mode == CompletionMode.CONTINUATION

        # Manual model ID input is only shown in manual mode
        for i in range(self.manual_model_id_layout.count()):
            widget = self.manual_model_id_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(is_manual)

        # Token picker is only shown in token-by-token mode
        self.token_picker_area.setVisible(is_token_by_token)

        # Prefill area behavior
        if is_manual:
            self.prefill_edit.setPlaceholderText("Not used in manual mode")
            self.prefill_edit.setEnabled(False)
        else:
            self.prefill_edit.setPlaceholderText("Enter prefill text here...")
            self.prefill_edit.setEnabled(True)

        # Completion area behavior
        if is_manual:
            self.completion_area.setReadOnly(False)
            self.completion_area.setPlaceholderText("Enter completion text manually...")
        else:
            self.completion_area.setReadOnly(True)
            self.completion_area.setPlaceholderText("Generated completion text...")

        # Continue button only visible in token-by-token mode when there's a prefix
        self.continue_generation_btn.setVisible(is_token_by_token and bool(self.token_by_token_prefix))

        # Update generate button text based on mode
        if is_token_by_token:
            self.generate_btn.setText("Next Token")
            self.generate_btn.setToolTip("Fetch next token candidates")
        elif is_continuation:
            self.generate_btn.setText("Continue")
            self.generate_btn.setToolTip("Continue truncated completion")
        else:
            self.generate_btn.setText("Generate")
            self.generate_btn.setToolTip("Generate completion with current parameters")

        # Update status label
        if is_manual:
            self.status_label.setText("Manual mode: Enter completion text and model ID, then save.")
        elif is_token_by_token:
            self.status_label.setText("Token-by-token mode: Click 'Next Token' to see candidates.")
        elif is_continuation:
            if self.current_completion:
                self.status_label.setText(f"Continuation mode: Continue completion from model {self.current_completion.model_id}")
            else:
                self.status_label.setText("Continuation mode: No completion set for continuation.")
        else:
            self.status_label.setText("")

    def generate_completion(self):
        """
        Generate a new completion with current parameters.
        
        Behavior depends on current mode:
        - REGULAR: Generate from prompt + optional prefill
        - CONTINUATION: Continue truncated completion
        - MANUAL: Save manually entered completion
        - TOKEN_BY_TOKEN: Fetch next token candidates and show picker
        """
        if not self.app:
            self.status_label.setText("Error: No app provider available")
            return

        # Dispatch based on mode
        if self.current_mode == CompletionMode.MANUAL:
            self._handle_manual_mode()
        elif self.current_mode == CompletionMode.CONTINUATION:
            self._handle_continuation_mode()
        elif self.current_mode == CompletionMode.TOKEN_BY_TOKEN:
            self._handle_token_by_token_mode()
        else:  # REGULAR
            self._handle_regular_mode()

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

    def _handle_continuation_mode(self) -> None:
        """Handle continuation mode for truncated completions."""
        if not self.current_completion:
            self.status_label.setText("Error: No completion set for continuation")
            return

        # Navigate up the widget hierarchy to find the WidgetSample
        widget_sample = self.parent()
        while widget_sample and not hasattr(widget_sample, "prompt_area"):
            widget_sample = widget_sample.parent()

        if not widget_sample:
            self.status_label.setText("Error: Cannot find widget sample")
            return

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating continuation...")
        if self.app.q_app:  # type: ignore
            self.app.q_app.processEvents()  # type: ignore # Force UI update

        # Get mapped model from current completion
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
                self.generate_btn.setEnabled(True)
        except (RuntimeError, ValueError) as e:
            self.status_label.setText(f"Error: {e}")
            self.generate_btn.setEnabled(True)

    def _handle_manual_mode(self) -> None:
        """Handle manual completion input mode."""
        # Import here to avoid circular imports
        from py_fade.providers.llm_response import LLMResponse  # pylint: disable=import-outside-toplevel

        # In manual mode, just enable save button if there's text
        completion_text = self.completion_area.toPlainText().strip()
        if not completion_text:
            self.status_label.setText("Error: No completion text entered")
            return

        model_id = self.manual_model_id_edit.text().strip() or "manual"

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

        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Manual completion ready to save (model: {model_id})")

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

        # Get or create controller
        mapped_model = self.app.providers_manager.get_mapped_model(self.model_combo.currentText())
        if not mapped_model:
            self.status_label.setText(f"Error: Model '{self.model_combo.currentText()}' not found")
            self.generate_btn.setEnabled(True)
            return

        prompt_text: str = widget_sample.prompt_area.toPlainText().strip()  # type: ignore
        context_length: int = widget_sample.context_length_field.value()  # type: ignore
        max_tokens: int = widget_sample.max_tokens_field.value()  # type: ignore

        try:
            if not self.token_by_token_controller:
                self.token_by_token_controller = self.app.get_or_create_text_generation_controller(
                    mapped_model, prompt_text, context_length=context_length, max_tokens=max_tokens)

            # Get current prefix (prefill + accumulated tokens)
            prefill_text = self.prefill_edit.toPlainText().strip()
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
        
        Appends selected token to current prefix and updates display.
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

        # Show continue button
        self.continue_generation_btn.setVisible(True)

        # Clear token picker
        self.token_picker_area.setWidget(None)
        self.token_picker_area.setVisible(False)

        self.status_label.setText(f"Token added: '{token.token_str}'. Click 'Next Token' for more or 'Continue' for regular generation.")

    def continue_from_token_by_token(self) -> None:
        """
        Continue regular generation from current token-by-token sequence.
        
        Uses the accumulated prefix as a high-fidelity prefill.
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

        self.continue_generation_btn.setEnabled(False)
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
            self.continue_generation_btn.setEnabled(True)
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
        self.continue_generation_btn.setEnabled(False)  # Disable after regular generation completes
        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Generated by {self.generated_completion.model_id}")

    def save_completion(self):
        """Save the generated completion and emit signal."""
        if not self.generated_completion:
            return

        self.completion_accepted.emit(self.generated_completion)
        self.status_label.setText("Completion saved!")

        # Reset for next generation (but keep parameters)
        self.generated_completion = None
        self.current_completion = None
        self.token_by_token_controller = None
        self.token_by_token_prefix = ""
        self.token_by_token_tokens = []
        self.completion_area.hide()
        self.token_picker_area.hide()
        self.save_btn.setEnabled(False)
        self.continue_generation_btn.setVisible(False)

        # Reset to regular mode
        self.mode_combo.setCurrentIndex(0)
