"""
Material-themed widget for viewing a single completion with inline actions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_completion_rating import CompletionRatingWidget
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon, QLabelWithIconAndText
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_completion_text_editor import CompletionTextEdit
from py_fade.data_formats.base_data_classes import CommonCompletionProtocol
from py_fade.providers.providers_manager import MappedModel
from py_fade.dataset.completion import PromptCompletion

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.providers.llm_response import LLMResponse

PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")


class CompletionFrame(QFrame):
    """Card-style shell that wraps completion metadata, rating control,
    and inline actions."""

    # Existing signals
    archive_toggled = pyqtSignal(object, bool)
    resume_requested = pyqtSignal(object)
    limited_continuation_requested = pyqtSignal(object)  # LLMResponse for limited continuation in beam mode
    evaluate_requested = pyqtSignal(object, object, object)  # completion, target_model, completion_frame

    # New signals for multi-mode support
    edit_requested = pyqtSignal(object)  # PromptCompletion
    discard_requested = pyqtSignal(object)  # PromptCompletion or LLMResponse
    save_requested = pyqtSignal(object)  # LLMResponse for beam mode
    pin_toggled = pyqtSignal(object, bool)  # LLMResponse, is_pinned
    beam_out_requested = pyqtSignal(int)  # token_index - clicked token in heatmap mode
    use_as_prefill_requested = pyqtSignal(str)  # completion_text - for beam mode

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
        self.limited_continuation_button: QPushButtonWithIcon | None = None
        self.evaluate_button: QPushButtonWithIcon | None = None
        self.edit_button: QPushButtonWithIcon | None = None
        self.discard_button: QPushButtonWithIcon | None = None
        self.save_button: QPushButtonWithIcon | None = None
        self.pin_button: QPushButtonWithIcon | None = None
        self.heatmap_button: QPushButtonWithIcon | None = None
        self.use_as_prefill_button: QPushButtonWithIcon | None = None

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
        self.text_edit = CompletionTextEdit(self, self)
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
        if self.actions_layout is None:
            raise RuntimeError("Actions layout not initialized.")

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

            # Resume button for truncated beams
            self.resume_button = QPushButtonWithIcon("resume", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.resume_button.setFlat(True)
            self.resume_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.resume_button.hide()  # Only shown for truncated completions
            self.actions_layout.addWidget(self.resume_button)

            # Limited continuation button for truncated unsaved beams
            self.limited_continuation_button = QPushButtonWithIcon("fast_forward", parent=self, icon_size=self.actions_icon_size,
                                                                   button_size=40)
            self.limited_continuation_button.setFlat(True)
            self.limited_continuation_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.limited_continuation_button.hide()  # Only shown for truncated unsaved completions
            self.actions_layout.addWidget(self.limited_continuation_button)

            # Archive button for saved beam completions
            self.archive_button = QPushButtonWithIcon("archive", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.archive_button.setFlat(True)
            self.archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.archive_button.hide()  # Only shown after beam is saved
            self.actions_layout.addWidget(self.archive_button)

            # Use as Prefill button for beam completions
            self.use_as_prefill_button = QPushButtonWithIcon("input", parent=self, icon_size=self.actions_icon_size, button_size=40)
            self.use_as_prefill_button.setFlat(True)
            self.use_as_prefill_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.use_as_prefill_button.setToolTip("Use this completion text as prefill")
            self.actions_layout.addWidget(self.use_as_prefill_button)

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
            if self.resume_button:
                self.resume_button.clicked.connect(self._on_resume_clicked)
            if self.limited_continuation_button:
                self.limited_continuation_button.clicked.connect(self._on_limited_continuation_clicked)
            if self.use_as_prefill_button:
                self.use_as_prefill_button.clicked.connect(self._on_use_as_prefill_clicked)

    def _log_rating_saved(self, rating: int) -> None:
        """Log rating persistence for debugging purposes."""

        self.log.debug("Saved rating %s for completion %s", rating, self.completion)

    def set_completion(self, completion: "PromptCompletion | LLMResponse") -> None:
        """Populate the frame with *completion* details."""

        self.completion = completion

        # Set model info
        model_id = completion.model_id
        self.model_label.setText(model_id)

        # Update temperature label and visibility based on mode and completion type
        self._update_temperature_label(completion)

        # Hide header widgets in beam mode unless it's a saved completion
        is_saved_beam = (self.display_mode == "beam" and isinstance(completion, PromptCompletion) and completion.id is not None)
        header_visible = self.display_mode == "sample" or is_saved_beam

        self.model_label.setVisible(header_visible)
        if self.temperature_label:
            self.temperature_label.setVisible(header_visible)

        self._update_status_icons()
        self.text_edit.set_completion(completion)

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
        self._update_status_icons()

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
                self.evaluate_button.setToolTip(f"Evaluate logprobs for '{self.target_model.model_id}'.")
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
        is_truncated = getattr(self.completion, "is_truncated", False)
        is_archived = getattr(self.completion, "is_archived", False)

        if self.save_button:
            self.save_button.setVisible(not is_saved)
        if self.pin_button:
            self.pin_button.setVisible(not is_saved)

        # Resume button for truncated completions (both saved and unsaved)
        if self.resume_button:
            if is_truncated and not is_archived:
                self.resume_button.show()
                self.resume_button.setToolTip("Resume generation from this truncated completion.")
            else:
                self.resume_button.hide()

        # Limited continuation button for truncated unsaved beams only
        if self.limited_continuation_button:
            if is_truncated and not is_saved and not is_archived:
                self.limited_continuation_button.show()
                self.limited_continuation_button.setToolTip("Generate limited continuation (Depth tokens only)")
            else:
                self.limited_continuation_button.hide()

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

        if self.completion.get_logprobs_for_model_id(self.target_model.model_id):
            return False
        return True

    def _on_archive_clicked(self) -> None:
        """Handle archive button click."""
        if not self.dataset.session or not hasattr(self.completion, "is_archived"):
            self.log.error("Cannot toggle archive state without an active dataset session or proper completion.")
            return

        completion = self.completion
        new_state = not completion.is_archived
        completion.is_archived = new_state

        # Clean alternative logprobs when archiving to save disk space
        if new_state and isinstance(completion, PromptCompletion):
            completion.clean_alternative_logprobs()

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
        """
        Handle evaluate button click.
        """
        self.evaluate_requested.emit(self.completion, self.target_model, self)

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

    def _on_limited_continuation_clicked(self) -> None:
        """Handle limited continuation button click for beam mode."""
        if self.display_mode != "beam":
            return
        self.limited_continuation_requested.emit(self.completion)

    def _on_use_as_prefill_clicked(self) -> None:
        """Handle use as prefill button click for beam mode."""
        if self.display_mode != "beam":
            return
        # Emit the completion text to be used as prefill
        self.use_as_prefill_requested.emit(self.completion.completion_text)

    def _on_heatmap_toggled(self, enabled: bool) -> None:
        """Handle heatmap button toggle."""
        self.is_heatmap_mode = enabled
        self.text_edit.set_heatmap_mode(enabled)

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

    def _update_status_icons(self) -> None:
        """Populate status icons based on completion properties."""
        self._clear_layout(self.status_layout)
        completion: CommonCompletionProtocol = self.completion

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

        if self.target_model:
            logprobs_for_model = completion.get_logprobs_for_model_id(self.target_model.model_id)
            self.log.debug("Checking logprobs for model '%s': %s", self.target_model.model_id, logprobs_for_model)
        else:
            self.log.debug("No target model set for logprob evaluation.")
            logprobs_for_model = None

        if logprobs_for_model:
            self.log.debug("min_logprob: %s, avg_logprob: %s", logprobs_for_model.min_logprob, logprobs_for_model.avg_logprob)
            if logprobs_for_model.min_logprob is not None:
                tooltip = (f"Logprobs min: {logprobs_for_model.min_logprob:.3f}, "
                           f"avg: {logprobs_for_model.avg_logprob:.3f}")

                # Add lowest logprob token to tooltip
                min_token = logprobs_for_model.get_min_logprob_token()
                if min_token:
                    tooltip += f"\nLowest token: '{min_token.token_str}' ({min_token.logprob:.3f})"

                color = logprob_to_qcolor(logprobs_for_model.min_logprob).name()

        # Always add metrics icon with appropriate color/tooltip
        self.status_layout.addWidget(QLabelWithIcon(
            "metrics",
            size=self.icons_size,
            color=color,
            tooltip=tooltip,
        ))

        # Is manually edited
        if completion.is_manual:
            self.status_layout.addWidget(
                QLabelWithIcon(
                    "edit",
                    size=self.icons_size,
                    color="orange",
                    tooltip=f"This completion was manually edited. Parent completion: {completion.parent_completion_id}, click to view.",
                ))

        self.status_layout.addStretch()

    def _can_show_heatmap(self, completion: CommonCompletionProtocol) -> bool:
        """
        Check if heatmap can be shown for this completion.
        """
        if not self.target_model:
            return False  # No target model set for logprob evaluation
        has_full_logprob = CommonCompletionProtocol.check_full_response_logprobs(completion, self.target_model.model_id)
        if not has_full_logprob:
            return False
        logprobs = completion.get_logprobs_for_model_id(self.target_model.model_id)
        self.text_edit.set_logprobs(logprobs)
        return True

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def on_heatmap_token_clicked(self, token_index: int) -> None:
        """
        Handle token click in heatmap mode.

        Emits beam_out_requested signal with token index to let parent widget handle the beam-out logic.
        """
        self.log.debug("Heatmap token clicked at index %d", token_index)
        self.beam_out_requested.emit(token_index)
