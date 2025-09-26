"""Material-themed widget for viewing and rating a single completion."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QMouseEvent, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.gui.auxillary import logprob_to_qcolor
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon, QLabelWithIconAndText

if TYPE_CHECKING:
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet


PREFILL_COLOR = QColor("#FFF9C4")
BEAM_TOKEN_COLOR = QColor("#C5E1A5")
EMPTY_STAR_COLOR = "#B0BEC5"
LOW_RATING_COLOR = "#d84315"
MID_RATING_COLOR = "#f9a825"
HIGH_RATING_COLOR = "#2e7d32"


class _StarButton(QToolButton):
    """Interactive button that emits half-star aware rating values."""

    hover_rating = pyqtSignal(int)
    rating_chosen = pyqtSignal(int)

    def __init__(self, star_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.star_index = star_index
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Return a slightly larger size hint to improve clickability."""

        hint = super().sizeHint()
        return QSize(max(hint.width(), 32), max(hint.height(), 32))

    def _rating_from_position(self, pos_x: float) -> int:
        width = max(1, self.width())
        fraction = pos_x / width
        half = 1 if fraction <= 0.5 else 2
        return (self.star_index - 1) * 2 + half

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Emit hover ratings while the pointer moves across the star."""

        if self.isEnabled():
            rating = self._rating_from_position(event.position().x())
            self.hover_rating.emit(rating)
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Highlight the star when the pointer enters its bounds."""

        if self.isEnabled():
            self.hover_rating.emit(self.star_index * 2)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Clear the hover highlight when the pointer leaves the star."""

        if self.isEnabled():
            self.hover_rating.emit(0)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Translate a click into a concrete rating value."""

        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            rating = self._rating_from_position(event.position().x())
            self.rating_chosen.emit(rating)
            event.accept()
            return
        super().mousePressEvent(event)


class CompletionRatingWidget(QFrame):
    """Five-star rating control that persists ratings per facet."""

    rating_saved = pyqtSignal(int)

    def __init__(self, dataset: "DatasetDatabase", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log = logging.getLogger("CompletionRatingWidget")
        self.dataset = dataset
        self.completion: "PromptCompletion | None" = None
        self.facet: "Facet | None" = None
        self.rating_record: "PromptCompletionRating | None" = None
        self.current_rating: int = 0
        self.hover_rating: int = 0
        self._star_icon_size = 28

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.header_label = QLabelWithIconAndText("star_rate", "Facet rating", size=13, parent=self)
        header_layout.addWidget(self.header_label)

        header_layout.addStretch()
        self.rating_value_label = QLabel("-- / 10", self)
        self.rating_value_label.setStyleSheet("font-weight: bold; color: #424242;")
        header_layout.addWidget(self.rating_value_label)

        layout.addLayout(header_layout)

        stars_layout = QHBoxLayout()
        stars_layout.setSpacing(4)

        self.star_buttons: list[_StarButton] = []
        for index in range(1, 6):
            button = _StarButton(index, self)
            button.setIconSize(QSize(self._star_icon_size, self._star_icon_size))
            button.setEnabled(False)
            stars_layout.addWidget(button)
            self.star_buttons.append(button)

        stars_layout.addStretch()
        layout.addLayout(stars_layout)

        self.helper_label = QLabel("Select a facet to rate this completion.", self)
        self.helper_label.setStyleSheet("color: #757575; font-size: 11px;")
        layout.addWidget(self.helper_label)

        self._apply_rating_to_stars(0)

    def _connect_signals(self) -> None:
        for button in self.star_buttons:
            button.hover_rating.connect(self._on_star_hover)
            button.rating_chosen.connect(self._on_star_clicked)

    def set_context(
        self,
        completion: "PromptCompletion | None",
        facet: "Facet | None",
    ) -> None:
        """Bind the widget to *completion* and *facet* and refresh UI state."""

        self.completion = completion
        self.facet = facet
        self.rating_record = None
        self.current_rating = 0
        self.hover_rating = 0

        if not completion or not facet:
            self._set_enabled_state(False)
            self._apply_rating_to_stars(0)
            self.rating_value_label.setText("-- / 10")
            self.helper_label.setText("Select a facet to rate this completion.")
            return

        try:
            self.rating_record = PromptCompletionRating.get(self.dataset, completion, facet)
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            self.log.error("Unable to fetch rating: %s", exc)
            self._set_enabled_state(False)
            self.helper_label.setText("Unable to load ratings: check dataset session.")
            return

        self.current_rating = self.rating_record.rating if self.rating_record else 0
        self._set_enabled_state(True)
        self._update_rating_labels()
        self._apply_rating_to_stars(self.current_rating)
        self._update_star_tooltips()

    def _set_enabled_state(self, enabled: bool) -> None:
        for button in self.star_buttons:
            button.setEnabled(enabled)

    def _update_star_tooltips(self) -> None:
        if not self.facet:
            tooltip = "Select a facet to rate this completion."
            for button in self.star_buttons:
                button.setToolTip(tooltip)
            return

        facet_name = self.facet.name
        if self.rating_record:
            tooltip = f"{facet_name}: {self.current_rating}/10"
        else:
            tooltip = f"Click to rate {facet_name}"

        for index, button in enumerate(self.star_buttons, start=1):
            base = (index - 1) * 2
            button.setToolTip(f"{tooltip} (≥ {base + 1}/10)")

    def _on_star_hover(self, rating: int) -> None:
        if self.rating_record is not None:
            return
        self.hover_rating = rating
        self._apply_rating_to_stars(rating or self.current_rating)
        self._update_helper_for_hover(rating)

    def _on_star_clicked(self, rating: int) -> None:
        if not self.completion or not self.facet:
            return

        if self.rating_record and self.rating_record.rating == rating:
            return

        if self.rating_record:
            answer = QMessageBox.question(
                self,
                "Update rating",
                (
                    f"Replace the existing rating ({self.rating_record.rating}/10) "
                    f"for facet '{self.facet.name}' with {rating}/10?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._apply_rating_to_stars(self.current_rating)
                self._update_helper_for_hover(0)
                return

        self._persist_rating(rating)

    def _persist_rating(self, rating: int) -> None:
        if not self.completion or not self.facet:
            return

        try:
            self.rating_record = PromptCompletionRating.set_rating(
                self.dataset,
                self.completion,
                self.facet,
                rating,
            )
        except ValueError as exc:
            self.log.error("Invalid rating: %s", exc)
            return

        self.current_rating = self.rating_record.rating
        self.hover_rating = 0
        self._apply_rating_to_stars(self.current_rating)
        self._update_rating_labels()
        self._update_star_tooltips()
        self.rating_saved.emit(self.current_rating)

    def _update_helper_for_hover(self, rating: int) -> None:
        if not self.facet:
            return
        if rating:
            self.helper_label.setText(
                f"Click to save {rating}/10 for '{self.facet.name}'."
            )
        elif self.rating_record:
            self.helper_label.setText(
                f"Saved {self.current_rating}/10 for '{self.facet.name}'."
            )
        else:
            self.helper_label.setText(
                f"Click a star to rate '{self.facet.name}'."
            )

    def _update_rating_labels(self) -> None:
        if not self.facet:
            self.rating_value_label.setText("-- / 10")
            return
        if self.rating_record:
            self.rating_value_label.setText(f"{self.current_rating} / 10")
            self.helper_label.setText(
                f"Saved {self.current_rating}/10 for '{self.facet.name}'."
            )
        else:
            self.rating_value_label.setText("Not rated")
            self.helper_label.setText(
                f"Click a star to rate '{self.facet.name}'."
            )

    def _color_for_rating(self, rating: int) -> str:
        if rating >= 8:
            return HIGH_RATING_COLOR
        if rating >= 5:
            return MID_RATING_COLOR
        if rating > 0:
            return LOW_RATING_COLOR
        return EMPTY_STAR_COLOR

    def _apply_rating_to_stars(self, rating: int) -> None:
        color = self._color_for_rating(rating)
        for index, button in enumerate(self.star_buttons, start=1):
            star_progress = rating - (index - 1) * 2
            if star_progress >= 2:
                icon = google_icon_font.pixmap(
                    "star_rate", size=self._star_icon_size, color=color, fill=1.0
                )
            elif star_progress == 1:
                icon = google_icon_font.pixmap(
                    "star_rate_half", size=self._star_icon_size, color=color, fill=1.0
                )
            else:
                icon = google_icon_font.pixmap(
                    "star_rate", size=self._star_icon_size, color=EMPTY_STAR_COLOR, fill=0.0
                )
            button.setIcon(QIcon(icon))


class CompletionFrame(QFrame):
    """Card-like presentation of a single completion and its metadata."""

    icons_size = 24

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

        self.rating_widget = CompletionRatingWidget(self.dataset, self)
        self.main_layout.addWidget(self.rating_widget)

    def connect_signals(self) -> None:
        """Wire internal signals for logging purposes."""

        self.rating_widget.rating_saved.connect(self._log_rating_saved)

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

    def set_facet(self, facet: "Facet | None") -> None:
        """Update the currently active facet and refresh rating display."""

        self.current_facet = facet
        self.rating_widget.set_context(self.completion, facet)

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
