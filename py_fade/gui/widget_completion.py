"""Material-themed widget for viewing a single completion with inline actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components import (
    CompletionRatingWidget,
    QLabelWithIcon,
    QLabelWithIconAndText,
    QPushButtonWithIcon,
)

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet


PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")
class CompletionFrame(QFrame):
    """Card-style shell that wraps completion metadata, rating control, and inline actions."""

    archive_toggled = pyqtSignal(object, bool)
    resume_requested = pyqtSignal(object)
    evaluate_requested = pyqtSignal(object, str)

    icons_size = 24
    actions_icon_size = 22
    def __init__(
        self,
        dataset: "DatasetDatabase",
        completion: "PromptCompletion",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.log = logging.getLogger("CompletionFrame")
        self.dataset = dataset
        self.completion = completion
        self.current_facet: "Facet | None" = None
        self.temperature_label: QWidget | None = None
        self.target_model: str | None = None

        self.actions_layout: QHBoxLayout | None = None
        self.archive_button: QPushButtonWithIcon | None = None
        self.resume_button: QPushButtonWithIcon | None = None
        self.evaluate_button: QPushButtonWithIcon | None = None

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

        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(6)
        self.model_label = QLabelWithIconAndText("model", "", size=14, parent=self)
        self.header_layout.addWidget(self.model_label)
        self.header_layout.addStretch()
        self.main_layout.addLayout(self.header_layout)

        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(6)
        self.main_layout.addLayout(self.status_layout)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_edit.setSizePolicy(policy)
        self.main_layout.addWidget(self.text_edit)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(0)

        self.rating_widget = CompletionRatingWidget(self.dataset, self, icon_size=self.actions_icon_size)
        self.actions_layout.addWidget(self.rating_widget)
        self.actions_layout.addStretch()

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

        self.main_layout.addLayout(self.actions_layout)

    def connect_signals(self) -> None:
        """Wire internal signals for logging purposes."""
        if self.archive_button is None or self.resume_button is None or self.evaluate_button is None:
            raise RuntimeError("Action buttons not initialized before connecting signals.")
        self.rating_widget.rating_saved.connect(self._log_rating_saved)
        self.archive_button.clicked.connect(self._on_archive_clicked)
        self.resume_button.clicked.connect(self._on_resume_clicked)
        self.evaluate_button.clicked.connect(self._on_evaluate_clicked)

    def _log_rating_saved(self, rating: int) -> None:
        """Log rating persistence for debugging purposes."""

        self.log.debug("Saved rating %s for completion %s", rating, self.completion.id)

    def set_completion(self, completion: "PromptCompletion") -> None:
        """Populate the frame with *completion* details."""

        self.completion = completion
        self.model_label.setText(completion.model_id)
        self._update_temperature_label(completion)
        self._populate_status_icons(completion)
        self._update_text_display(completion)
        self.rating_widget.set_context(self.completion, self.current_facet)
        self._update_action_buttons()

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the currently active facet and refresh rating display."""

        self.current_facet = facet
        self.rating_widget.set_context(self.completion, facet)
        self._update_action_buttons()

    def set_target_model(self, model_name: str | None) -> None:
        """Set the active evaluation model for logprob checks."""

        self.target_model = model_name
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        if not self.archive_button or not self.resume_button or not self.evaluate_button:
            return

        self._update_archive_button()

        if self.completion.is_truncated:
            self.resume_button.show()
            self.resume_button.setToolTip("Resume generation from this truncated completion.")
        else:
            self.resume_button.hide()

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

    def _update_archive_button(self) -> None:
        if not self.archive_button:
            return

        if self.completion.is_archived:
            self.archive_button.setIcon(google_icon_font.as_icon("unarchive"))
            self.archive_button.setToolTip("Unarchive this completion")
        else:
            self.archive_button.setIcon(google_icon_font.as_icon("archive"))
            self.archive_button.setToolTip("Archive this completion")

    def _needs_evaluate_button(self) -> bool:
        if not self.target_model:
            return False

        if not self.completion.logprobs:
            return True

        return not any(
            logprob.logprobs_model_id == self.target_model for logprob in self.completion.logprobs
        )

    def _on_archive_clicked(self) -> None:
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

    def _on_resume_clicked(self) -> None:
        self.resume_requested.emit(self.completion)

    def _on_evaluate_clicked(self) -> None:
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

    def _update_text_display(self, completion: "PromptCompletion") -> None:
        text = completion.completion_text or ""
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self._clear_highlights()
        if text:
            self._highlight_prefill_and_beam(text, completion)
        self.text_edit.blockSignals(False)

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
