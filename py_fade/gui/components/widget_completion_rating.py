"""Compact star rating component used across completion widgets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QWidget

from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.gui.auxillary.aux_google_icon_font import google_icon_font

if TYPE_CHECKING:  # pragma: no cover - imports only used for type checking
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet

EMPTY_STAR_COLOR = "#B0BEC5"
LOW_RATING_COLOR = "#d84315"
MID_RATING_COLOR = "#f9a825"
HIGH_RATING_COLOR = "#2e7d32"


# QToolButton
class _StarButton(QPushButton):
    """Interactive button that emits half-star aware rating values."""

    hover_rating = pyqtSignal(int)
    rating_chosen = pyqtSignal(int)

    def __init__(self, star_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.star_index = star_index
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setStyleSheet("QPushButton { border: none; }")

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


class CompletionRatingWidget(QWidget):
    """Five-star rating control that persists ratings per facet."""

    rating_saved = pyqtSignal(int)

    def __init__(
        self,
        dataset: "DatasetDatabase",
        parent: QWidget | None = None,
        icon_size: int = 24,
    ) -> None:
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.dataset = dataset
        self.completion: "PromptCompletion | None" = None
        self.facet: "Facet | None" = None
        self.rating_record: "PromptCompletionRating | None" = None
        self.current_rating: int = 0
        self.hover_rating: int = 0
        self._star_icon_size = icon_size

        self.setup_ui()
        self.connect_signals()
        self._apply_rating_to_stars(0)

    def setup_ui(self) -> None:
        """Create the compact row of star buttons."""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # self.setFixedSize(QSize(self._star_icon_size * 10 + 8, self._star_icon_size * 3 + 4))
        button_size = int(self._star_icon_size * 1.5)
        self.star_buttons: list[_StarButton] = []
        for index in range(1, 6):
            button = _StarButton(index, self)
            button.setIconSize(QSize(self._star_icon_size, self._star_icon_size))
            # button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedSize(QSize(button_size, button_size))
            button.setEnabled(False)
            layout.addWidget(button)
            self.star_buttons.append(button)

    def connect_signals(self) -> None:
        """Wire hover and click handlers for the star buttons."""

        for button in self.star_buttons:
            button.hover_rating.connect(self._on_star_hover)
            button.rating_chosen.connect(self._on_star_clicked)

    def set_icon_size(self, size: int) -> None:
        """Adjust icon size for the star buttons to match parent layouts."""
        self.log.info("Setting star icon size to %d", size)
        self._star_icon_size = size
        for button in self.star_buttons:
            button.setIconSize(QSize(size, size))
        self._apply_rating_to_stars(self.current_rating or self.hover_rating)

    def set_context(
        self,
        completion: "PromptCompletion | None",
        facet: "Facet | None",
    ) -> None:
        """Bind the widget to *completion*/*facet* and refresh UI state."""

        self.completion = completion
        self.facet = facet
        self.rating_record = None
        self.current_rating = 0
        self.hover_rating = 0

        if not completion or not facet:
            self._set_enabled_state(False)
            self._apply_rating_to_stars(0)
            self._update_star_tooltips()
            return

        try:
            self.rating_record = PromptCompletionRating.get(self.dataset, completion, facet)
        except RuntimeError as exc:  # pragma: no cover - defensive guard
            self.log.error("Unable to fetch rating: %s", exc)
            self._set_enabled_state(False)
            self._apply_rating_to_stars(0)
            self._update_star_tooltips()
            return

        self.current_rating = self.rating_record.rating if self.rating_record else 0
        self._set_enabled_state(True)
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

    def _on_star_clicked(self, rating: int) -> None:
        if not self.completion or not self.facet:
            return

        if self.rating_record:
            # Offer to remove or change existing rating
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Remove or change rating")
            msg_box.setText(f"Current rating for facet '{self.facet.name}' is {self.rating_record.rating}/10.\n"
                            f"You are trying to set it to {rating}/10.\n\n"
                            f"What would you like to do?")
            msg_box.setIcon(QMessageBox.Icon.Question)

            remove_button = msg_box.addButton("Remove rating", QMessageBox.ButtonRole.DestructiveRole)
            change_button = msg_box.addButton("Change rating", QMessageBox.ButtonRole.ActionRole)
            cancel_button = msg_box.addButton(QMessageBox.StandardButton.Cancel)
            msg_box.setDefaultButton(cancel_button)

            msg_box.exec()
            clicked_button = msg_box.clickedButton()

            if clicked_button == remove_button:
                self._remove_rating()
            elif clicked_button == change_button:
                # Allow changing to a different rating by resetting hover
                self._persist_rating(rating)
            else:
                # Cancel - restore current rating display
                self._apply_rating_to_stars(self.current_rating)
            return

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
        self._update_star_tooltips()
        self.rating_saved.emit(self.current_rating)

    def _remove_rating(self) -> None:
        """Remove the current rating from the database and reset UI state."""

        if not self.rating_record:
            return

        try:
            self.rating_record.delete(self.dataset)
        except RuntimeError as exc:
            self.log.error("Failed to delete rating: %s", exc)
            return

        self.rating_record = None
        self.current_rating = 0
        self.hover_rating = 0
        self._apply_rating_to_stars(0)
        self._update_star_tooltips()
        self.rating_saved.emit(0)

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
                icon = google_icon_font.pixmap("star_rate", size=self._star_icon_size, color=color, fill=1.0)
            elif star_progress == 1:
                icon = google_icon_font.pixmap("star_rate_half", size=self._star_icon_size, color=color, fill=1.0)
            else:
                icon = google_icon_font.pixmap("star_rate", size=self._star_icon_size, color=EMPTY_STAR_COLOR, fill=0.0)
            # self.log.info("Set icon to %s, size %d, dpr %d", icon, self._star_icon_size, icon.devicePixelRatio())
            button.setIcon(QIcon(icon))
            # opt = QStyleOptionToolButton()
            # button.initStyleOption(opt)
            # print("opt.iconSize:", opt.iconSize, "iconSize():", button.iconSize(), "rect:", opt.rect)


__all__ = ["CompletionRatingWidget"]
