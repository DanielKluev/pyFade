"""
Material-themed widget for viewing a single completion with inline actions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QToolTip,
)

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_completion_rating import CompletionRatingWidget
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon, QLabelWithIconAndText
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse

PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")


class HeatmapTextEdit(QTextEdit):
    """Custom QTextEdit that shows tooltips for logprobs in heatmap mode."""

    def __init__(self, completion_frame: 'CompletionFrame', parent: QWidget | None = None):
        super().__init__(parent)
        self.completion_frame = completion_frame
        self._logprobs_data_cache: list = []
        self._token_positions_cache: list = []  # List of (start_pos, end_pos, logprob)

    def update_heatmap_cache(self, logprobs_data: list, text: str) -> None:
        """Update cached token positions for tooltip lookups."""
        self._logprobs_data_cache = logprobs_data
        self._token_positions_cache = []

        text_pos = 0
        for token_data in logprobs_data:
            token = token_data.get("token", "")
            logprob = token_data.get("logprob")

            if not token or logprob is None:
                continue

            # Find token position in text
            token_len = len(token)
            if text_pos + token_len > len(text):
                break

            if text[text_pos:text_pos + token_len] == token:
                self._token_positions_cache.append((text_pos, text_pos + token_len, logprob))
                text_pos += token_len
            else:
                # Try to find token starting from current position
                found_pos = text.find(token, text_pos)
                if found_pos != -1 and found_pos <= text_pos + 10:  # Don't search too far ahead
                    self._token_positions_cache.append((found_pos, found_pos + token_len, logprob))
                    text_pos = found_pos + token_len
                else:
                    text_pos += 1  # Skip character if token not found nearby

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Handle mouse move events to show tooltips in heatmap mode."""
        super().mouseMoveEvent(event)

        if not self.completion_frame.is_heatmap_mode or not self._token_positions_cache:
            return

        # Get cursor position at mouse location
        cursor = self.cursorForPosition(event.pos())
        cursor_pos = cursor.position()

        # Find which token contains this position
        for start_pos, end_pos, logprob in self._token_positions_cache:
            if start_pos <= cursor_pos < end_pos:
                # Show tooltip with logprob value
                tooltip_text = f"logprob: {logprob:.4f}"
                QToolTip.showText(event.globalPos(), tooltip_text, self)
                return

        # Hide tooltip if not over a token
        QToolTip.hideText()


class CompletionFrame(QFrame):
    """Card-style shell that wraps completion metadata, rating control,
    and inline actions."""

    # Existing signals
    archive_toggled = pyqtSignal(object, bool)
    resume_requested = pyqtSignal(object)
    evaluate_requested = pyqtSignal(object, str)

    # New signals for multi-mode support
    edit_requested = pyqtSignal(object)  # PromptCompletion
    discard_requested = pyqtSignal(object)  # PromptCompletion or LLMResponse
    save_requested = pyqtSignal(object)  # LLMResponse for beam mode
    pin_toggled = pyqtSignal(object, bool)  # LLMResponse, is_pinned

    icons_size = 24
    actions_icon_size = 22

    def __init__(
        self,
        dataset: "DatasetDatabase",
        completion: "PromptCompletion | LLMResponse",
        parent: QWidget | None = None,
        *,
        display_mode: str = "sample",
    ) -> None:
        super().__init__(parent)
        self.log = logging.getLogger("CompletionFrame")
        self.dataset = dataset
        self.completion = completion
        self.display_mode = display_mode
        self.current_facet: "Facet | None" = None
        self.temperature_label: QWidget | None = None
        self.target_model: MappedModel | None = None

        # Track pin state for beam mode (transient, not persisted)
        self.is_pinned = False

        # Track heatmap display mode (transient, not persisted)
        self.is_heatmap_mode = False

        self.actions_layout: QHBoxLayout | None = None
        self.archive_button: QPushButtonWithIcon | None = None
        self.resume_button: QPushButtonWithIcon | None = None
        self.evaluate_button: QPushButtonWithIcon | None = None
        self.edit_button: QPushButtonWithIcon | None = None
        self.discard_button: QPushButtonWithIcon | None = None
        self.save_button: QPushButtonWithIcon | None = None
        self.pin_button: QPushButtonWithIcon | None = None
        self.heatmap_button: QPushButtonWithIcon | None = None

        self.setup_ui()
        self.connect_signals()
        self.set_completion(completion)

    def setup_ui(self) -> None:
        """Create the frame layout and child widgets."""

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("completionFrame")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # Header (model info) - hidden in beam mode unless completion is saved
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(6)
        self.model_label = QLabelWithIconAndText("model", "", size=14, parent=self)
        self.header_layout.addWidget(self.model_label)
        self.header_layout.addStretch()
        self.main_layout.addLayout(self.header_layout)

        # Status icons layout
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(6)
        self.main_layout.addLayout(self.status_layout)

        # Text display
        self.text_edit = HeatmapTextEdit(self, self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setMouseTracking(True)  # Enable mouse tracking for tooltips
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_edit.setSizePolicy(policy)
        self.main_layout.addWidget(self.text_edit)

        # Actions layout
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(0)

        # Rating widget - hidden in beam mode
        if self.display_mode == "sample":
            self.rating_widget = CompletionRatingWidget(self.dataset, self, icon_size=self.actions_icon_size)
            self.actions_layout.addWidget(self.rating_widget)
            self.actions_layout.addStretch()

        # Action buttons - mode-specific
        self._setup_action_buttons()

        self.main_layout.addLayout(self.actions_layout)

    def _setup_action_buttons(self) -> None:
        """Setup action buttons based on display mode."""

        # Common buttons
        self.discard_button = QPushButtonWithIcon("delete", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.discard_button.setFlat(True)
        self.discard_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_button.setToolTip("Discard this completion")
        self.actions_layout.addWidget(self.discard_button)

        # Heatmap toggle button - shown when completion has full logprobs
        self.heatmap_button = QPushButtonWithIcon("heatmap", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.heatmap_button.setFlat(True)
        self.heatmap_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.heatmap_button.setCheckable(True)
        self.heatmap_button.setToolTip("Toggle logprob heatmap view")
        self.heatmap_button.hide()  # Hidden by default, shown when logprobs available
        self.actions_layout.addWidget(self.heatmap_button)

        if self.display_mode == "sample":
            # Sample mode buttons
            self.edit_button = QPushButtonWithIcon("edit", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.edit_button.setFlat(True)
            self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.edit_button.setToolTip("Edit this completion")
            self.actions_layout.addWidget(self.edit_button)

            self.resume_button = QPushButtonWithIcon("resume", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.resume_button.setFlat(True)
            self.resume_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.resume_button.hide()
            self.actions_layout.addWidget(self.resume_button)

            self.evaluate_button = QPushButtonWithIcon("search_insights", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.evaluate_button.setFlat(True)
            self.evaluate_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.evaluate_button.hide()
            self.actions_layout.addWidget(self.evaluate_button)

            self.archive_button = QPushButtonWithIcon("archive", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.archive_button.setFlat(True)
            self.archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.actions_layout.addWidget(self.archive_button)

        elif self.display_mode == "beam":
            # Beam mode buttons
            self.save_button = QPushButtonWithIcon("save", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.save_button.setFlat(True)
            self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.save_button.setToolTip("Save this beam as completion")
            self.actions_layout.addWidget(self.save_button)

            self.pin_button = QPushButtonWithIcon("keep", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.pin_button.setFlat(True)
            self.pin_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.pin_button.setToolTip("Pin/unpin this beam")
            self.actions_layout.addWidget(self.pin_button)

            # Archive button for saved beam completions
            self.archive_button = QPushButtonWithIcon("archive", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.archive_button.setFlat(True)
            self.archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.archive_button.hide()  # Only shown after beam is saved
            self.actions_layout.addWidget(self.archive_button)

    def connect_signals(self) -> None:
        """Wire internal signals for logging purposes."""
        # Connect rating widget for sample mode
        if self.display_mode == "sample" and hasattr(self, "rating_widget"):
            self.rating_widget.rating_saved.connect(self._log_rating_saved)

        # Connect common buttons
        if self.discard_button:
            self.discard_button.clicked.connect(self._on_discard_clicked)
        if self.archive_button:
            self.archive_button.clicked.connect(self._on_archive_clicked)
        if self.heatmap_button:
            self.heatmap_button.toggled.connect(self._on_heatmap_toggled)

        # Connect sample mode buttons
        if self.display_mode == "sample":
            if self.edit_button:
                self.edit_button.clicked.connect(self._on_edit_clicked)
            if self.resume_button:
                self.resume_button.clicked.connect(self._on_resume_clicked)
            if self.evaluate_button:
                self.evaluate_button.clicked.connect(self._on_evaluate_clicked)

        # Connect beam mode buttons
        elif self.display_mode == "beam":
            if self.save_button:
                self.save_button.clicked.connect(self._on_save_clicked)
            if self.pin_button:
                self.pin_button.clicked.connect(self._on_pin_clicked)

    def _log_rating_saved(self, rating: int) -> None:
        """Log rating persistence for debugging purposes."""

        self.log.debug("Saved rating %s for completion %s", rating, self.completion.id)

    def set_completion(self, completion: "PromptCompletion | LLMResponse") -> None:
        """Populate the frame with *completion* details."""

        self.completion = completion

        # Set model info
        model_id = completion.model_id
        self.model_label.setText(model_id)

        # Update temperature label and visibility based on mode and completion type
        self._update_temperature_label(completion)

        # Hide header widgets in beam mode unless it's a saved completion
        is_saved_beam = (self.display_mode == "beam" and hasattr(completion, "id") and completion.id is not None)
        header_visible = self.display_mode == "sample" or is_saved_beam

        self.model_label.setVisible(header_visible)
        if self.temperature_label:
            self.temperature_label.setVisible(header_visible)

        self._populate_status_icons(completion)
        self._update_text_display(completion)

        # Update rating widget for sample mode
        if self.display_mode == "sample" and hasattr(self, "rating_widget"):
            self.rating_widget.set_context(self.completion, self.current_facet)

        self._update_action_buttons()

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the currently active facet and refresh rating display."""

        self.current_facet = facet
        if self.display_mode == "sample" and hasattr(self, "rating_widget"):
            self.rating_widget.set_context(self.completion, facet)
        self._update_action_buttons()

    def set_target_model(self, mapped_model: MappedModel | None) -> None:
        """Set the active evaluation model for logprob checks."""

        self.target_model = mapped_model
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Update button visibility and states based on completion and mode."""
        # Update heatmap button visibility based on logprobs availability
        if self.heatmap_button:
            can_show_heatmap = self._can_show_heatmap(self.completion)
            self.heatmap_button.setVisible(can_show_heatmap)
            if can_show_heatmap:
                self.heatmap_button.setChecked(self.is_heatmap_mode)

        if self.display_mode == "sample":
            self._update_sample_mode_buttons()
        elif self.display_mode == "beam":
            self._update_beam_mode_buttons()

    def _update_sample_mode_buttons(self) -> None:
        """Update buttons for sample mode."""
        if not hasattr(self.completion, "id"):
            return

        completion = self.completion  # It's a PromptCompletion in sample mode

        # Archive button
        self._update_archive_button()

        # Resume button
        if self.resume_button:
            if completion.is_truncated and not completion.is_archived:
                self.resume_button.show()
                self.resume_button.setToolTip("Resume generation from this truncated completion.")
            else:
                self.resume_button.hide()

        # Evaluate button
        if self.evaluate_button:
            needs_evaluate = self._needs_evaluate_button()
            self.evaluate_button.setVisible(needs_evaluate)
            if needs_evaluate and self.target_model:
                self.evaluate_button.setToolTip(f"Evaluate logprobs for '{self.target_model}'.")
            elif needs_evaluate:
                self.evaluate_button.setToolTip("Evaluate logprobs for the active model.")
            else:
                self.evaluate_button.setToolTip("Logprobs already available for the active model.")

    def _update_beam_mode_buttons(self) -> None:
        """Update buttons for beam mode."""
        # Pin button visual state
        if self.pin_button:
            if self.is_pinned:
                self.pin_button.setIcon(google_icon_font.as_icon("keep_off"))
                self.pin_button.setToolTip("Unpin this beam")
                self.setStyleSheet("border: 2px solid #ff8c00; background-color: #fff8dc;")
            else:
                self.pin_button.setIcon(google_icon_font.as_icon("keep"))
                self.pin_button.setToolTip("Pin this beam")
                self.setStyleSheet("")

        # Show/hide buttons based on whether this beam has been saved
        is_saved = (hasattr(self.completion, "id") and getattr(self.completion, "id", None) is not None)

        if self.save_button:
            self.save_button.setVisible(not is_saved)
        if self.pin_button:
            self.pin_button.setVisible(not is_saved)
        if self.archive_button:
            self.archive_button.setVisible(is_saved)
            if is_saved:
                self._update_archive_button()

    def _update_archive_button(self) -> None:
        """Update archive button icon and tooltip based on completion state."""
        if not self.archive_button or not hasattr(self.completion, "is_archived"):
            return

        completion = self.completion
        if completion.is_archived:
            self.archive_button.setIcon(google_icon_font.as_icon("unarchive"))
            self.archive_button.setToolTip("Unarchive this completion")
        else:
            self.archive_button.setIcon(google_icon_font.as_icon("archive"))
            self.archive_button.setToolTip("Archive this completion")

    def _needs_evaluate_button(self) -> bool:
        """Check if the evaluate button should be shown."""
        if not self.target_model:
            return False

        # Only applies to PromptCompletion objects in sample mode
        if not hasattr(self.completion, "logprobs"):
            return False

        if not self.completion.logprobs:
            return True

        return not any(logprob.logprobs_model_id == self.target_model for logprob in self.completion.logprobs)

    def _on_archive_clicked(self) -> None:
        """Handle archive button click."""
        if not self.dataset.session or not hasattr(self.completion, "is_archived"):
            self.log.error("Cannot toggle archive state without an active dataset session or proper completion.")
            return

        completion = self.completion
        new_state = not completion.is_archived
        completion.is_archived = new_state
        try:
            self.dataset.commit()
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            self.log.error("Failed to persist archive change: %s", exc)
            completion.is_archived = not new_state
            return

        self._update_action_buttons()
        self.archive_toggled.emit(self.completion, new_state)

    def _on_resume_clicked(self) -> None:
        """Handle resume button click."""
        self.resume_requested.emit(self.completion)

    def _on_evaluate_clicked(self) -> None:
        """Handle evaluate button click."""
        target = self.target_model or self.completion.model_id
        self.evaluate_requested.emit(self.completion, target)

    def _on_edit_clicked(self) -> None:
        """Handle edit button click."""
        self.edit_requested.emit(self.completion)

    def _on_discard_clicked(self) -> None:
        """Handle discard button click."""
        # Check if completion is persisted (has an ID)
        has_id = hasattr(self.completion, "id") and getattr(self.completion, "id", None) is not None

        if has_id:
            # Show confirmation dialog for persisted completions
            reply = QMessageBox.question(
                self,
                "Confirm Discard",
                "This completion is saved in the database. "
                "Discarding will permanently delete it. Are you sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        self.discard_requested.emit(self.completion)

    def _on_save_clicked(self) -> None:
        """Handle save button click for beam mode."""
        if self.display_mode != "beam":
            return
        self.save_requested.emit(self.completion)

    def _on_pin_clicked(self) -> None:
        """Handle pin button click for beam mode."""
        if self.display_mode != "beam":
            return
        self.is_pinned = not self.is_pinned
        self._update_action_buttons()
        self.pin_toggled.emit(self.completion, self.is_pinned)

    def _on_heatmap_toggled(self, enabled: bool) -> None:
        """Handle heatmap button toggle."""
        self.is_heatmap_mode = enabled
        self._update_text_display(self.completion)

    def _update_temperature_label(self, completion: "PromptCompletion | LLMResponse") -> None:
        """Update temperature label based on completion parameters."""
        if self.temperature_label is not None:
            self.header_layout.removeWidget(self.temperature_label)
            self.temperature_label.deleteLater()
            self.temperature_label = None

        temperature = completion.temperature
        top_k = completion.top_k

        if temperature is not None and top_k == 1:
            new_label: QWidget = QLabelWithIcon(
                "mode_cool",
                size=14,
                parent=self,
                color="blue",
                tooltip=self._temperature_tooltip(completion),
            )
        else:
            new_label = QLabelWithIconAndText(
                "temperature",
                f"{temperature}, K: {top_k}",
                size=14,
                parent=self,
                color="red",
                tooltip=self._temperature_tooltip(completion),
            )
        self.temperature_label = new_label
        self.header_layout.addWidget(new_label)

    @staticmethod
    def _temperature_tooltip(completion: "PromptCompletion | LLMResponse") -> str:
        """Build tooltip text describing sampling parameters."""
        return f"Temperature: {completion.temperature}, top_k: {completion.top_k}"

    def _populate_status_icons(self, completion: "PromptCompletion | LLMResponse") -> None:
        """Populate status icons based on completion properties."""
        self._clear_layout(self.status_layout)

        # Check for is_truncated
        is_truncated = getattr(completion, "is_truncated", None)
        if is_truncated:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "is_truncated",
                    size=self.icons_size,
                    color="red",
                    tooltip="Completion was truncated due to max tokens limit.",
                ))

        # Check for prefill
        prefill = getattr(completion, "prefill", None)
        if prefill:
            self.status_layout.addWidget(QLabelWithIcon(
                "prefill",
                size=self.icons_size,
                tooltip=f"Prefill used: {prefill}",
            ))

        # Check for beam_token
        beam_token = getattr(completion, "beam_token", None)
        if beam_token:
            self.status_layout.addWidget(QLabelWithIcon(
                "beaming",
                size=self.icons_size,
                tooltip=f"Beam token used: '{beam_token}'",
            ))

        # Check for logprobs - handle both PromptCompletion and LLMResponse
        tooltip = "No logprobs available."
        color = "gray"

        if hasattr(completion, "logprobs") and completion.logprobs:
            if hasattr(completion, "id"):  # PromptCompletion
                if completion.logprobs and completion.logprobs[0].min_logprob is not None:
                    logprob = completion.logprobs[0].min_logprob
                    tooltip = (f"Logprobs min: {logprob:.3f}, "
                               f"avg: {completion.logprobs[0].avg_logprob:.3f}")
                    color = logprob_to_qcolor(logprob).name()
            else:  # LLMResponse
                if hasattr(completion, "min_logprob") and completion.min_logprob is not None:
                    logprob = completion.min_logprob
                    tooltip = f"Logprobs min: {logprob:.3f}"
                    color = logprob_to_qcolor(logprob).name()

        # Always add metrics icon with appropriate color/tooltip
        self.status_layout.addWidget(QLabelWithIcon(
            "metrics",
            size=self.icons_size,
            color=color,
            tooltip=tooltip,
        ))

        self.status_layout.addStretch()

    def _update_text_display(self, completion: "PromptCompletion | LLMResponse") -> None:
        """Update text display based on completion content."""
        # Get text content - different attribute names for different types
        if hasattr(completion, "completion_text"):  # PromptCompletion
            text = completion.completion_text or ""
        elif hasattr(completion, "full_response_text"):  # LLMResponse
            text = completion.full_response_text or ""
        else:
            text = ""

        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self._clear_highlights()

        if text:
            if self.is_heatmap_mode and self._can_show_heatmap(completion):
                self._highlight_logprob_heatmap(text, completion)
            else:
                self._highlight_prefill_and_beam(text, completion)
        self.text_edit.blockSignals(False)

    def _clear_highlights(self) -> None:
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.endEditBlock()

    def _highlight_prefill_and_beam(self, text: str, completion: "PromptCompletion | LLMResponse") -> None:
        """Highlight prefill and beam token sections in the text."""
        document_cursor = self.text_edit.textCursor()

        def apply_highlight(start: int, end: int, color: QColor) -> None:
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)
            cursor = QTextCursor(document_cursor)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)

        prefill = getattr(completion, "prefill", None)
        beam_token = getattr(completion, "beam_token", None)

        if prefill:
            start = text.find(prefill)
            if start >= 0:
                end = start + len(prefill)
                apply_highlight(start, end, PREFILL_COLOR)
                if beam_token:
                    beam_start = text.find(beam_token, start)
                    if beam_start >= 0:
                        beam_end = beam_start + len(beam_token)
                        apply_highlight(beam_start, beam_end, BEAM_TOKEN_COLOR)
                    else:
                        self.log.debug("Beam token '%s' not found within completion text.", beam_token)
            else:
                self.log.debug("Prefill '%s' not found in completion text.", prefill)
        elif beam_token:
            beam_start = text.find(beam_token)
            if beam_start >= 0:
                apply_highlight(beam_start, beam_start + len(beam_token), BEAM_TOKEN_COLOR)

    def _can_show_heatmap(self, completion: "PromptCompletion | LLMResponse") -> bool:
        """Check if heatmap can be shown for this completion."""
        self.log.info("Checking if heatmap can be shown for completion %s, target model is '%s'", completion, self.target_model)
        # For LLMResponse, check if logprobs cover full response
        if hasattr(completion, "logprobs") and completion.logprobs:
            self.log.info("Completion has logprobs data.")
            if hasattr(completion, "check_full_response_logprobs"):
                return completion.check_full_response_logprobs()

            # For PromptCompletion, check if target model logprobs are available and valid
            if hasattr(completion, "id") and self.target_model:
                target_logprobs = None
                for logprob in completion.logprobs:
                    self.log.info("Examining logprobs for model '%s', target is '%s'.", logprob.logprobs_model_id,
                                  self.target_model.model_id)
                    if logprob.logprobs_model_id == self.target_model.model_id:
                        target_logprobs = logprob.logprobs
                        break

                if target_logprobs:
                    self.log.info("Found logprobs for target model '%s'.", self.target_model.model_id)
                    # Check if tokens cover full text
                    return self._check_logprobs_cover_text(completion.completion_text or "", target_logprobs)

        return False

    def _check_logprobs_cover_text(self, text: str, logprobs: list) -> bool:
        """Check if logprobs tokens cover the full text."""
        if not logprobs or not text:
            return False

        text_pos = 0
        for logprob_entry in logprobs:
            token = logprob_entry.get("token", "")
            if not token:
                return False

            # Check if token matches the text at current position
            if text_pos + len(token) > len(text):
                return False
            if text[text_pos:text_pos + len(token)] != token:
                return False

            text_pos += len(token)

        return text_pos == len(text)

    def _highlight_logprob_heatmap(self, text: str, completion: "PromptCompletion | LLMResponse") -> None:
        """Apply logprob-based color highlighting to tokens."""
        logprobs_data = self._get_logprobs_for_heatmap(completion)
        if not logprobs_data:
            return

        # Update the text edit cache for tooltips
        self.text_edit.update_heatmap_cache(logprobs_data, text)

        document_cursor = self.text_edit.textCursor()
        text_pos = 0

        for token_data in logprobs_data:
            token = token_data.get("token", "")
            logprob = token_data.get("logprob")

            if not token or logprob is None:
                continue

            # Find token position in text
            token_len = len(token)
            if text_pos + token_len > len(text):
                break
            if text[text_pos:text_pos + token_len] != token:
                # Try to find token starting from current position
                found_pos = text.find(token, text_pos)
                if found_pos == -1 or found_pos > text_pos + 10:  # Don't search too far ahead
                    text_pos += 1  # Skip character if token not found nearby
                    continue
                text_pos = found_pos

            # Apply color based on logprob
            color = logprob_to_qcolor(logprob)

            # Create highlight format
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)

            # Apply highlight
            cursor = QTextCursor(document_cursor)
            cursor.setPosition(text_pos)
            cursor.setPosition(text_pos + token_len, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)

            text_pos += token_len

    def _get_logprobs_for_heatmap(self, completion: "PromptCompletion | LLMResponse") -> list:
        """Get logprobs data for heatmap display."""
        if hasattr(completion, "logprobs") and completion.logprobs:
            # For LLMResponse
            if hasattr(completion.logprobs[0], "token"):
                return [{"token": lp.token, "logprob": lp.logprob} for lp in completion.logprobs if lp.logprob is not None]

            # For PromptCompletion with target model
            if hasattr(completion, "id") and self.target_model:
                for logprob in completion.logprobs:
                    if logprob.logprobs_model_id == self.target_model.model_id:
                        return logprob.logprobs

        return []

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
