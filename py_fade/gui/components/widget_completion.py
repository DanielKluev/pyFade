"""Material-themed widget for viewing a single completion with inline actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_completion_rating import CompletionRatingWidget
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon, QLabelWithIconAndText

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse


PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")
class CompletionFrame(QFrame):
    """Card-style shell that wraps completion metadata, rating control, and inline actions."""

    archive_toggled = pyqtSignal(object, bool)
    resume_requested = pyqtSignal(object)
    evaluate_requested = pyqtSignal(object, str)
    # New signals for enhanced functionality
    discarded = pyqtSignal(object)  # CompletionFrame or PromptCompletion
    edit_requested = pyqtSignal(object)  # PromptCompletion  
    saved = pyqtSignal(object, object)  # CompletionFrame, PromptCompletion (newly created)
    pinned = pyqtSignal(object, bool)  # CompletionFrame, is_pinned state

    icons_size = 24
    actions_icon_size = 22
    
    def __init__(
        self,
        dataset: "DatasetDatabase",
        completion: "PromptCompletion | None" = None,
        beam: "LLMResponse | None" = None,
        display_mode: str = "sample", 
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.log = logging.getLogger("CompletionFrame")
        
        if display_mode not in ("sample", "beam"):
            raise ValueError(f"Invalid display_mode: {display_mode}. Must be 'sample' or 'beam'.")
        
        if display_mode == "sample" and not completion:
            raise ValueError("completion parameter is required for sample mode.")
        if display_mode == "beam" and not beam:
            raise ValueError("beam parameter is required for beam mode.")
            
        self.dataset = dataset
        self.completion = completion
        self.beam = beam
        self.display_mode = display_mode
        self.current_facet: "Facet | None" = None
        self.temperature_label: QWidget | None = None
        self.target_model: str | None = None
        
        # Beam mode state
        self.is_pinned = False
        self.is_accepted = False

        self.actions_layout: QHBoxLayout | None = None
        self.archive_button: QPushButtonWithIcon | None = None
        self.resume_button: QPushButtonWithIcon | None = None
        self.evaluate_button: QPushButtonWithIcon | None = None
        # New buttons for enhanced functionality
        self.discard_button: QPushButtonWithIcon | None = None
        self.edit_button: QPushButtonWithIcon | None = None
        self.save_button: QPushButtonWithIcon | None = None
        self.pin_button: QPushButtonWithIcon | None = None

        self.setup_ui()
        self.connect_signals()
        
        if display_mode == "sample" and completion:
            self.set_completion(completion)
        elif display_mode == "beam" and beam:
            self.set_beam(beam)

    def setup_ui(self) -> None:
        """Create the frame layout and child widgets."""

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("completionFrame")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # Header layout (model info) - hidden in beam mode initially
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(6)
        self.model_label = QLabelWithIconAndText("model", "", size=14, parent=self)
        self.header_layout.addWidget(self.model_label)
        self.header_layout.addStretch()
        self.main_layout.addLayout(self.header_layout)

        # Status layout (icons for various states)
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(6)
        self.main_layout.addLayout(self.status_layout)

        # Text display
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_edit.setSizePolicy(policy)
        self.main_layout.addWidget(self.text_edit)

        # Actions layout
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(0)

        # Mode-specific widgets
        if self.display_mode == "sample":
            self._setup_sample_mode_actions()
        else:  # beam mode
            self._setup_beam_mode_actions()

        self.main_layout.addLayout(self.actions_layout)

    def _setup_sample_mode_actions(self) -> None:
        """Set up action buttons for sample mode."""
        # Rating widget
        self.rating_widget = CompletionRatingWidget(self.dataset, self, icon_size=self.actions_icon_size)
        self.actions_layout.addWidget(self.rating_widget)
        self.actions_layout.addStretch()

        # Discard button
        self.discard_button = QPushButtonWithIcon("delete", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.discard_button.setFlat(True)
        self.discard_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_button.setToolTip("Discard this completion")
        self.actions_layout.addWidget(self.discard_button)

        # Edit button
        self.edit_button = QPushButtonWithIcon("edit", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.edit_button.setFlat(True)
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.setToolTip("Edit this completion")
        self.actions_layout.addWidget(self.edit_button)

        # Resume button
        self.resume_button = QPushButtonWithIcon("resume", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.resume_button.setFlat(True)
        self.resume_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resume_button.hide()
        self.actions_layout.addWidget(self.resume_button)

        # Evaluate button
        self.evaluate_button = QPushButtonWithIcon("search_insights", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.evaluate_button.setFlat(True)
        self.evaluate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.evaluate_button.hide()
        self.actions_layout.addWidget(self.evaluate_button)

        # Archive button
        self.archive_button = QPushButtonWithIcon("archive", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.archive_button.setFlat(True)
        self.archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_layout.addWidget(self.archive_button)

    def _setup_beam_mode_actions(self) -> None:
        """Set up action buttons for beam mode."""
        # For beam mode, add stretch first to align buttons to the right
        self.actions_layout.addStretch()

        # Discard button
        self.discard_button = QPushButtonWithIcon("delete", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.discard_button.setFlat(True)
        self.discard_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_button.setToolTip("Discard this beam")
        self.actions_layout.addWidget(self.discard_button)

        # Save button (only for unsaved beams)
        self.save_button = QPushButtonWithIcon("save", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.save_button.setFlat(True)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setToolTip("Save this beam as completion")
        self.actions_layout.addWidget(self.save_button)

        # Pin button 
        self.pin_button = QPushButtonWithIcon("keep", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.pin_button.setFlat(True)
        self.pin_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_button.setToolTip("Pin this beam")
        self.actions_layout.addWidget(self.pin_button)
        
        # Archive button (only for saved beam completions)
        self.archive_button = QPushButtonWithIcon("archive", parent=self, icon_size=self.actions_icon_size, button_size=40)
        self.archive_button.setFlat(True)
        self.archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.archive_button.hide()  # Initially hidden, shown after saving
        self.actions_layout.addWidget(self.archive_button)

    def connect_signals(self) -> None:
        """Wire internal signals for logging purposes."""
        # Common buttons that exist in both modes
        if self.discard_button:
            self.discard_button.clicked.connect(self._on_discard_clicked)
        if self.archive_button:
            self.archive_button.clicked.connect(self._on_archive_clicked)
        
        # Sample mode specific buttons
        if self.display_mode == "sample":
            if self.rating_widget:
                self.rating_widget.rating_saved.connect(self._log_rating_saved)
            if self.edit_button:
                self.edit_button.clicked.connect(self._on_edit_clicked)
            if self.resume_button:
                self.resume_button.clicked.connect(self._on_resume_clicked)
            if self.evaluate_button:
                self.evaluate_button.clicked.connect(self._on_evaluate_clicked)
        
        # Beam mode specific buttons  
        if self.display_mode == "beam":
            if self.save_button:
                self.save_button.clicked.connect(self._on_save_clicked)
            if self.pin_button:
                self.pin_button.clicked.connect(self._on_pin_clicked)

    def _log_rating_saved(self, rating: int) -> None:
        """Log rating persistence for debugging purposes."""

        self.log.debug("Saved rating %s for completion %s", rating, self.completion.id)

    def set_completion(self, completion: "PromptCompletion") -> None:
        """Populate the frame with *completion* details."""
        if self.display_mode != "sample":
            raise ValueError("set_completion can only be called in sample mode")

        self.completion = completion
        self.model_label.setText(completion.model_id)
        self._update_temperature_label(completion)
        self._populate_status_icons(completion)
        self._update_text_display_from_completion(completion)
        if self.rating_widget:
            self.rating_widget.set_context(self.completion, self.current_facet)
        self._update_action_buttons()

    def set_beam(self, beam: "LLMResponse") -> None:
        """Populate the frame with beam details."""
        if self.display_mode != "beam":
            raise ValueError("set_beam can only be called in beam mode")

        self.beam = beam
        # In beam mode, initially hide model/temperature info by hiding the label
        self.model_label.setVisible(False)
        # Update text display with beam response
        self._update_text_display_from_beam(beam)
        self._populate_beam_status_icons(beam)
        self._update_action_buttons()

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the currently active facet and refresh rating display."""

        self.current_facet = facet
        if self.display_mode == "sample" and self.rating_widget and self.completion:
            self.rating_widget.set_context(self.completion, facet)
        self._update_action_buttons()

    def set_target_model(self, model_name: str | None) -> None:
        """Set the active evaluation model for logprob checks."""

        self.target_model = model_name
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        if self.display_mode == "sample":
            self._update_sample_action_buttons()
        else:  # beam mode
            self._update_beam_action_buttons()

    def _update_sample_action_buttons(self) -> None:
        """Update visibility and state of sample mode action buttons."""
        if not self.completion:
            return

        if self.archive_button:
            self._update_archive_button()

        if self.resume_button:
            if self.completion.is_truncated and not self.completion.is_archived:
                self.resume_button.show()
                self.resume_button.setToolTip("Resume generation from this truncated completion.")
            else:
                self.resume_button.hide()

        if self.evaluate_button:
            needs_evaluate = self._needs_evaluate_button()
            self.evaluate_button.setVisible(needs_evaluate)
            if needs_evaluate and self.target_model:
                self.evaluate_button.setToolTip(
                    f"Evaluate logprobs for '{self.target_model}'."
                )
            elif needs_evaluate:
                self.evaluate_button.setToolTip("Evaluate logprobs for the active model.")
            else:
                self.evaluate_button.setToolTip("Logprobs already available for the active model.")

    def _update_beam_action_buttons(self) -> None:
        """Update visibility and state of beam mode action buttons."""
        # Show/hide buttons based on whether beam has been saved
        is_saved = self.completion is not None  # If we have a completion, this beam was saved
        
        if self.save_button:
            self.save_button.setVisible(not is_saved)
        
        if self.archive_button:
            self.archive_button.setVisible(is_saved)
            if is_saved:
                self._update_archive_button()
        
        # Pin button style update
        if self.pin_button:
            if self.is_pinned:
                self.pin_button.setToolTip("Unpin this beam")
                # TODO: Update styling to show pinned state
            else:
                self.pin_button.setToolTip("Pin this beam")

    def _update_archive_button(self) -> None:
        if not self.archive_button or not self.completion:
            return

        if self.completion.is_archived:
            self.archive_button.setIcon(google_icon_font.as_icon("unarchive"))
            self.archive_button.setToolTip("Unarchive this completion")
        else:
            self.archive_button.setIcon(google_icon_font.as_icon("archive"))
            self.archive_button.setToolTip("Archive this completion")

    def _needs_evaluate_button(self) -> bool:
        if not self.target_model or not self.completion:
            return False

        if not self.completion.logprobs:
            return True

        return not any(
            logprob.logprobs_model_id == self.target_model for logprob in self.completion.logprobs
        )

    def _on_archive_clicked(self) -> None:
        if self.display_mode != "sample" and not self.completion:
            self.log.error("Cannot archive in beam mode without saved completion.")
            return
            
        if not self.dataset.session:
            self.log.error("Cannot toggle archive state without an active dataset session.")
            return

        new_state = not self.completion.is_archived
        self.completion.is_archived = new_state
        try:
            self.dataset.commit()
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            self.log.error("Failed to persist archive change: %s", exc)
            self.completion.is_archived = not new_state
            return

        self._update_action_buttons()
        self.archive_toggled.emit(self.completion, new_state)

    def _on_discard_clicked(self) -> None:
        """Handle discard button click with confirmation for persisted completions."""
        if self.display_mode == "sample" and self.completion:
            # Check if completion is persisted (has ID)
            if self.completion.id:
                reply = QMessageBox.question(
                    self,
                    "Confirm Discard",
                    "This completion is saved in the database. Discarding will permanently delete it. Are you sure?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            self.discarded.emit(self.completion)
        elif self.display_mode == "beam":
            # For beams, always allow discard without confirmation since they're transient
            self.discarded.emit(self)

    def _on_edit_clicked(self) -> None:
        """Handle edit button click - only available in sample mode."""
        if self.display_mode == "sample" and self.completion:
            self.edit_requested.emit(self.completion)

    def _on_save_clicked(self) -> None:
        """Handle save button click - only available in beam mode."""
        if self.display_mode == "beam" and self.beam:
            # TODO: Create PromptCompletion from beam data and save to database
            # For now, emit signal to let parent handle the save logic
            self.saved.emit(self, None)  # Parent will create the completion

    def _on_pin_clicked(self) -> None:
        """Handle pin/unpin button click - only available in beam mode."""
        if self.display_mode == "beam":
            self.is_pinned = not self.is_pinned
            self._update_action_buttons()  # Update button appearance
            self.pinned.emit(self, self.is_pinned)

    def _on_resume_clicked(self) -> None:
        if self.display_mode == "sample" and self.completion:
            self.resume_requested.emit(self.completion)

    def _on_evaluate_clicked(self) -> None:
        if self.display_mode == "sample" and self.completion:
            target = self.target_model or self.completion.model_id
            self.evaluate_requested.emit(self.completion, target)

    def _update_temperature_label(self, completion: "PromptCompletion") -> None:
        if self.temperature_label is not None:
            self.header_layout.removeWidget(self.temperature_label)
            self.temperature_label.deleteLater()
            self.temperature_label = None
        if completion.temperature is not None and completion.top_k == 1:
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
                f"{completion.temperature}, K: {completion.top_k}",
                size=14,
                parent=self,
                color="red",
                tooltip=self._temperature_tooltip(completion),
            )
        self.temperature_label = new_label
        self.header_layout.addWidget(new_label)

    @staticmethod
    def _temperature_tooltip(completion: "PromptCompletion") -> str:
        """Build tooltip text describing sampling parameters."""

        return f"Temperature: {completion.temperature}, top_k: {completion.top_k}"

    def _populate_status_icons(self, completion: "PromptCompletion") -> None:
        self._clear_layout(self.status_layout)

        if completion.is_truncated:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "is_truncated",
                    size=self.icons_size,
                    color="red",
                    tooltip="Completion was truncated due to max tokens limit.",
                )
            )

        if completion.prefill:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "prefill",
                    size=self.icons_size,
                    tooltip=f"Prefill used: {completion.prefill}",
                )
            )

        if completion.beam_token:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "beaming",
                    size=self.icons_size,
                    tooltip=f"Beam token used: '{completion.beam_token}'",
                )
            )

        if completion.logprobs and completion.logprobs[0].min_logprob is not None:
            logprob = completion.logprobs[0].min_logprob
            tooltip = (
                f"Logprobs min: {logprob:.3f}, avg: {completion.logprobs[0].avg_logprob:.3f}"
            )
            color = logprob_to_qcolor(logprob).name()
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "metrics",
                    size=self.icons_size,
                    color=color,
                    tooltip=tooltip,
                )
            )
        else:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "metrics",
                    size=self.icons_size,
                    color="gray",
                    tooltip="No logprobs available.",
                )
            )

        self.status_layout.addStretch()

    def _update_text_display_from_completion(self, completion: "PromptCompletion") -> None:
        """Update text display from completion data."""
        text = completion.completion_text or ""
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self._clear_highlights()
        if text:
            self._highlight_prefill_and_beam(text, completion)
        self.text_edit.blockSignals(False)

    def _update_text_display_from_beam(self, beam: "LLMResponse") -> None:
        """Update text display from beam data."""
        text = beam.full_response_text or ""
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self._clear_highlights()
        # TODO: Add beam-specific highlighting if needed
        self.text_edit.blockSignals(False)

    def _populate_beam_status_icons(self, beam: "LLMResponse") -> None:
        """Populate status icons for beam mode."""
        self._clear_layout(self.status_layout)
        
        # Show beam-specific status information
        stats_text = f"Tokens: {len(beam.full_response_text.split())}"
        if hasattr(beam, "min_logprob") and beam.min_logprob is not None:
            stats_text += f" | Min logprob: {beam.min_logprob:.3f}"
            
        # Add a simple label instead of complex status icons for beams
        from PyQt6.QtWidgets import QLabel
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("font-size: 11px; color: #666;")
        self.status_layout.addWidget(stats_label)
        
        self.status_layout.addStretch()

    def _clear_highlights(self) -> None:
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.endEditBlock()

    def _highlight_prefill_and_beam(
        self, text: str, completion: "PromptCompletion"
    ) -> None:
        document_cursor = self.text_edit.textCursor()

        def apply_highlight(start: int, end: int, color: QColor) -> None:
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(color)
            cursor = QTextCursor(document_cursor)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)

        if completion.prefill:
            prefill = completion.prefill
            start = text.find(prefill)
            if start >= 0:
                end = start + len(prefill)
                apply_highlight(start, end, PREFILL_COLOR)
                if completion.beam_token:
                    beam = completion.beam_token
                    beam_start = text.find(beam, start)
                    if beam_start >= 0:
                        beam_end = beam_start + len(beam)
                        apply_highlight(beam_start, beam_end, BEAM_TOKEN_COLOR)
                    else:
                        self.log.debug(
                            "Beam token '%s' not found within completion text.", beam
                        )
            else:
                self.log.debug("Prefill '%s' not found in completion text.", prefill)
        elif completion.beam_token:
            beam = completion.beam_token
            beam_start = text.find(beam)
            if beam_start >= 0:
                apply_highlight(beam_start, beam_start + len(beam), BEAM_TOKEN_COLOR)

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
