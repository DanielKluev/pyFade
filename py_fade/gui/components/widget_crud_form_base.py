"""Reusable base form widget that wires up standard CRUD UI patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_label_with_icon import QLabelWithIconAndText


@dataclass(frozen=True)
class CrudButtonStyles:
    """Styling presets applied to the primary CRUD button row."""

    save: str = "QPushButton { background-color: #1976D2; color: white; padding: 8px 16px; }"
    cancel: str = "QPushButton { background-color: #757575; color: white; padding: 8px 16px; }"
    delete: str = "QPushButton { background-color: #d32f2f; color: white; padding: 8px 16px; }"


class CrudFormWidget(QWidget):
    """Shared helper that assembles a header, validation label, and CRUD buttons."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        header_icon: str,
        header_title: str,
        header_color: str,
        button_styles: CrudButtonStyles | None = None,
        minimum_size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(parent)

        if minimum_size:
            self.setMinimumSize(*minimum_size)

        self._button_styles = button_styles or CrudButtonStyles()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        self.header_layout = QHBoxLayout()
        self.header_label = QLabelWithIconAndText(
            header_icon,
            header_title,
            parent=self,
            size=18,
        )
        self.header_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {header_color};"
        )
        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        self.main_layout.addLayout(self.header_layout)

        self.form_container = QWidget(self)
        self.form_layout = QVBoxLayout(self.form_container)
        self.form_layout.setSpacing(12)
        self.main_layout.addWidget(self.form_container)

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.validation_label.setWordWrap(True)
        self.validation_label.hide()
        self.main_layout.addWidget(self.validation_label)

        self.main_layout.addStretch(1)

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(8)

        self.save_button = QPushButtonWithIcon("save", "Save", parent=self)
        self.save_button.setStyleSheet(self._button_styles.save)
        self.save_button.clicked.connect(self._on_save_clicked)  # type: ignore[arg-type]
        self.button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButtonWithIcon("cancel", "Cancel", parent=self)
        self.cancel_button.setStyleSheet(self._button_styles.cancel)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)  # type: ignore[arg-type]
        self.button_layout.addWidget(self.cancel_button)

        self.button_layout.addStretch(1)

        self.delete_button = QPushButtonWithIcon("delete", "Delete", parent=self)
        self.delete_button.setStyleSheet(self._button_styles.delete)
        self.delete_button.clicked.connect(self._on_delete_clicked)  # type: ignore[arg-type]
        self.button_layout.addWidget(self.delete_button)

        self.main_layout.addLayout(self.button_layout)

        self.build_form(self.form_layout)

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------
    def build_form(self, form_layout: QVBoxLayout) -> None:
        """Populate *form_layout* with the specific controls for the widget."""

        raise NotImplementedError

    def handle_save(self) -> None:
        """Persist the current form state."""

        raise NotImplementedError

    def handle_delete(self) -> None:
        """Delete the currently bound entity."""

        raise NotImplementedError

    def handle_cancel(self) -> None:
        """Handle reverting the form back to the last saved state."""

        raise NotImplementedError

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def set_header_text(self, text: str) -> None:
        """Update the header label while keeping icon and styling."""

        self.header_label.setText(text)

    def add_header_widget(self, widget: QWidget) -> None:
        """Append *widget* to the header row next to the label."""

        widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.header_layout.addWidget(widget)

    def insert_button(self, index: int, widget: QWidget) -> None:
        """Insert an additional button into the CRUD button layout."""

        self.button_layout.insertWidget(index, widget)

    def set_delete_visible(self, visible: bool) -> None:
        """Toggle the visibility of the delete button."""

        self.delete_button.setVisible(visible)

    def set_validation_errors(self, errors: Iterable[str]) -> None:
        """Show validation feedback and update the save button state."""

        error_list = list(errors)
        if error_list:
            self.validation_label.setText("\n".join(error_list))
            self.validation_label.show()
            self.save_button.setEnabled(False)
        else:
            self.validation_label.hide()
            self.save_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Internal slot adapters
    # ------------------------------------------------------------------
    def _on_save_clicked(self) -> None:
        self.handle_save()

    def _on_delete_clicked(self) -> None:
        self.handle_delete()

    def _on_cancel_clicked(self) -> None:
        self.handle_cancel()
