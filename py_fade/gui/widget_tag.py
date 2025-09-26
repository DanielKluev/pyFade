"""Interactive widget for authoring and managing dataset tags.

The :class:`WidgetTag` class exposes a faceted-material inspired editor that
mirrors the UX patterns used across the rest of pyFADE. It supports creating
new tags, updating existing ones, and deleting tags from the active dataset.
The widget is instantiated by :class:`py_fade.gui.widget_dataset_top.WidgetDatasetTop`
when the user navigates to a tag through the sidebar or creates a new tag.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal

from PyQt6.QtWidgets import (
    QLabel,
    QMessageBox,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.tag import Tag

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetTag(QWidget):
    """Material-themed editor that provides CRUD operations for :class:`Tag`."""

    SCOPE_CHOICES = [
        ("samples", "Samples only"),
        ("completions", "Completions only"),
        (Tag.DEFAULT_SCOPE, "Samples & completions"),
    ]

    tag_saved = pyqtSignal(object)
    tag_deleted = pyqtSignal(object)
    tag_cancelled = pyqtSignal()

    app: "pyFadeApp"
    dataset: DatasetDatabase
    tag: Tag | None

    def __init__(
        self,
        parent: QWidget | None,
        app: "pyFadeApp",
        dataset: DatasetDatabase,
        tag: Tag | None,
    ) -> None:
        """Build the widget and populate its fields from *tag* when provided."""

        super().__init__(parent)
        self.log = logging.getLogger("WidgetTag")
        self.app = app
        self.dataset = dataset
        self.tag = tag

        self._build_ui()
        self.set_tag(tag)

    def _build_ui(self) -> None:
        """Create and wire all UI controls used by the tag editor."""

        self.setMinimumSize(360, 280)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        self.header_label = QLabelWithIcon("label", "Tag Details")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00796B;")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        form_group = QGroupBox("Tag Information")
        form_group_layout = QVBoxLayout(form_group)
        form_group_layout.setSpacing(12)

        # Name field
        name_container = QVBoxLayout()
        name_label = QLabel("Name:")
        name_label.setStyleSheet("font-weight: bold;")
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Enter tag name…")
        self.name_field.textChanged.connect(self.validate_form)
        name_container.addWidget(name_label)
        name_container.addWidget(self.name_field)
        form_group_layout.addLayout(name_container)

        # Description field
        description_container = QVBoxLayout()
        description_label = QLabel("Description:")
        description_label.setStyleSheet("font-weight: bold;")
        self.description_field = QPlainTextEdit()
        self.description_field.setPlaceholderText("Describe how the tag should be used…")
        self.description_field.setMaximumHeight(120)
        self.description_field.textChanged.connect(self.validate_form)
        description_container.addWidget(description_label)
        description_container.addWidget(self.description_field)
        form_group_layout.addLayout(description_container)

        # Scope selector
        scope_container = QVBoxLayout()
        scope_label = QLabel("Scope:")
        scope_label.setStyleSheet("font-weight: bold;")
        self.scope_combo = QComboBox()
        self.scope_combo.setEditable(False)
        for value, label in self.SCOPE_CHOICES:
            self.scope_combo.addItem(label, value)
        self.scope_combo.currentIndexChanged.connect(self.validate_form)
        scope_container.addWidget(scope_label)
        scope_container.addWidget(self.scope_combo)
        form_group_layout.addLayout(scope_container)

        # Read-only metadata fields
        self.total_samples_field = QLineEdit()
        self.total_samples_field.setReadOnly(True)
        self.total_samples_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        self.date_created_field = QLineEdit()
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        total_samples_layout = QHBoxLayout()
        total_samples_label = QLabel("Total Samples:")
        total_samples_label.setStyleSheet("font-weight: bold;")
        total_samples_layout.addWidget(total_samples_label)
        total_samples_layout.addWidget(self.total_samples_field)
        total_samples_layout.addStretch()

        date_created_layout = QHBoxLayout()
        date_created_label = QLabel("Date Created:")
        date_created_label.setStyleSheet("font-weight: bold;")
        date_created_layout.addWidget(date_created_label)
        date_created_layout.addWidget(self.date_created_field)
        date_created_layout.addStretch()

        form_group_layout.addLayout(total_samples_layout)
        form_group_layout.addLayout(date_created_layout)

        main_layout.addWidget(form_group)

        # Validation message label
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.validation_label.setWordWrap(True)
        self.validation_label.hide()
        main_layout.addWidget(self.validation_label)

        main_layout.addStretch(1)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.save_button = QPushButtonWithIcon("save", "Save")
        self.save_button.setStyleSheet("QPushButton { background-color: #00796B; color: white; padding: 8px 16px; }")
        self.save_button.clicked.connect(self.save_tag)

        self.cancel_button = QPushButtonWithIcon("cancel", "Cancel")
        self.cancel_button.setStyleSheet("QPushButton { background-color: #757575; color: white; padding: 8px 16px; }")
        self.cancel_button.clicked.connect(self.cancel_editing)

        self.delete_button = QPushButtonWithIcon("delete", "Delete")
        self.delete_button.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; padding: 8px 16px; }")
        self.delete_button.clicked.connect(self.delete_tag)

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)

        main_layout.addLayout(button_layout)

    def set_tag(self, tag: Tag | None) -> None:
        """Populate the form with *tag* or reset it for a new tag."""

        self.tag = tag

        if tag is None:
            self.log.debug("Preparing widget for new tag entry")
            self.header_label.setText("New Tag")
            self.name_field.setText("")
            self.description_field.setPlainText("")
            self.total_samples_field.setText("0")
            self.date_created_field.setText("Will be set on save")
            self.delete_button.hide()
            default_index = self.scope_combo.findData(Tag.DEFAULT_SCOPE)
            self.scope_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        else:
            self.log.debug("Loading tag into editor: id=%s name=%s", tag.id, tag.name)
            self.header_label.setText(f"Edit Tag: {tag.name}")
            self.name_field.setText(tag.name)
            self.description_field.setPlainText(tag.description)
            self.total_samples_field.setText(str(tag.total_samples))
            self.date_created_field.setText(tag.date_created.strftime("%Y-%m-%d %H:%M:%S"))
            self.delete_button.show()
            index = self.scope_combo.findData(tag.scope)
            if index >= 0:
                self.scope_combo.setCurrentIndex(index)
            else:
                fallback = self.scope_combo.findData(Tag.DEFAULT_SCOPE)
                self.scope_combo.setCurrentIndex(fallback if fallback >= 0 else 0)

        self.validate_form()

    def validate_form(self) -> None:
        """Validate user input and toggle the save button/validation message."""

        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()

        errors: list[str] = []

        if not name:
            errors.append("Name is required")
        elif len(name) < 2:
            errors.append("Name must be at least 2 characters")
        elif len(name) > 100:
            errors.append("Name must be less than 100 characters")
        else:
            try:
                existing = Tag.get_by_name(self.dataset, name)
            except RuntimeError as exc:
                errors.append(str(exc))
            else:
                if existing and (self.tag is None or existing.id != self.tag.id):
                    errors.append("A tag with this name already exists")

        if not description:
            errors.append("Description is required")
        elif len(description) < 5:
            errors.append("Description must be at least 5 characters")
        elif len(description) > 2000:
            errors.append("Description must be less than 2000 characters")

        scope_value = self.scope_combo.currentData()
        try:
            Tag.normalize_scope(scope_value)
        except ValueError as exc:
            errors.append(str(exc))

        if errors:
            self.validation_label.setText("\n".join(errors))
            self.validation_label.show()
            self.save_button.setEnabled(False)
        else:
            self.validation_label.hide()
            self.save_button.setEnabled(True)

    def save_tag(self) -> None:
        """Persist the current form data to the dataset."""

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()
        scope_value = self.scope_combo.currentData()

        try:
            normalized_scope = Tag.normalize_scope(scope_value)
            if self.tag is None:
                self.log.debug("Creating tag with name=%s", name)
                self.tag = Tag.create(self.dataset, name, description, scope=normalized_scope)
            else:
                self.log.debug("Updating tag id=%s", self.tag.id)
                self.tag.update(self.dataset, name=name, description=description, scope=normalized_scope)

            self.dataset.session.flush()
            self.dataset.session.commit()
            if self.tag is not None:
                self.dataset.session.refresh(self.tag)

        except Exception as exc:  # noqa: BLE001 - surface message to user
            self.log.exception("Failed to save tag", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save tag: {exc}")
            return

        QMessageBox.information(self, "Success", f"Tag '{self.tag.name}' saved successfully!")
        self.tag_saved.emit(self.tag)
        self.set_tag(self.tag)

    def delete_tag(self) -> None:
        """Delete the current tag from the dataset after confirmation."""

        if not self.tag or not self.tag.id:
            return

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the tag '{self.tag.name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            self.log.debug("Deletion cancelled for tag id=%s", self.tag.id)
            return

        try:
            deleted_tag = self.tag
            self.log.debug("Deleting tag id=%s", deleted_tag.id if deleted_tag else None)
            if deleted_tag is not None:
                deleted_tag.delete(self.dataset)
            self.dataset.session.commit()
        except Exception as exc:  # noqa: BLE001 - communicate the failure
            self.log.exception("Failed to delete tag", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete tag: {exc}")
            return

        QMessageBox.information(self, "Success", "Tag deleted successfully!")
        if deleted_tag is not None:
            self.tag_deleted.emit(deleted_tag)
        self.set_tag(None)

    def cancel_editing(self) -> None:
        """Prompt the user and emit :pyattr:`tag_cancelled` if confirmed."""

        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Cancel editing this tag? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.log.debug("Editing cancelled by user")
            self.tag_cancelled.emit()
            self.set_tag(self.tag)