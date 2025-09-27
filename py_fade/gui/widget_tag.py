"""Interactive widget for authoring and managing dataset tags.

The :class:`WidgetTag` class exposes a faceted-material inspired editor that
mirrors the UX patterns used across the rest of pyFADE. It supports creating
new tags, updating existing ones, and deleting tags from the active dataset.
The widget is instantiated by :class:`py_fade.gui.widget_dataset_top.WidgetDatasetTop`
when the user navigates to a tag through the sidebar or creates a new tag.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.tag import Tag
from py_fade.gui.components.widget_crud_form_base import CrudFormWidget
from py_fade.gui.gui_helpers import (
    build_crud_button_styles,
    validate_description,
    validate_entity_name,
)

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetTag(CrudFormWidget):
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
        self.log = logging.getLogger("WidgetTag")
        self.app = app
        self.dataset = dataset
        self.tag = tag

        button_styles = build_crud_button_styles(save_color="#00796B")

        super().__init__(
            parent,
            header_icon="label",
            header_title="Tag Details",
            header_color="#00796B",
            button_styles=button_styles,
            minimum_size=(360, 280),
        )

        self.set_tag(tag)

    def build_form(self, form_layout: QVBoxLayout) -> None:
        """Create all tag-specific input controls."""

        form_group = QGroupBox("Tag Information", parent=self)
        group_layout = QVBoxLayout(form_group)
        group_layout.setSpacing(12)

        name_container = QVBoxLayout()
        name_label = QLabel("Name:", parent=form_group)
        name_label.setStyleSheet("font-weight: bold;")
        self.name_field = QLineEdit(parent=form_group)
        self.name_field.setPlaceholderText("Enter tag name…")
        self.name_field.textChanged.connect(self.validate_form)  # type: ignore[arg-type]
        name_container.addWidget(name_label)
        name_container.addWidget(self.name_field)
        group_layout.addLayout(name_container)

        description_container = QVBoxLayout()
        description_label = QLabel("Description:", parent=form_group)
        description_label.setStyleSheet("font-weight: bold;")
        self.description_field = QPlainTextEdit(parent=form_group)
        self.description_field.setPlaceholderText("Describe how the tag should be used…")
        self.description_field.setMaximumHeight(120)
        self.description_field.textChanged.connect(self.validate_form)  # type: ignore[arg-type]
        description_container.addWidget(description_label)
        description_container.addWidget(self.description_field)
        group_layout.addLayout(description_container)

        scope_container = QVBoxLayout()
        scope_label = QLabel("Scope:", parent=form_group)
        scope_label.setStyleSheet("font-weight: bold;")
        self.scope_combo = QComboBox(parent=form_group)
        self.scope_combo.setEditable(False)
        for value, label in self.SCOPE_CHOICES:
            self.scope_combo.addItem(label, value)
        self.scope_combo.currentIndexChanged.connect(self.validate_form)  # type: ignore[arg-type]
        scope_container.addWidget(scope_label)
        scope_container.addWidget(self.scope_combo)
        group_layout.addLayout(scope_container)

        self.total_samples_field = QLineEdit(parent=form_group)
        self.total_samples_field.setReadOnly(True)
        self.total_samples_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        self.date_created_field = QLineEdit(parent=form_group)
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        total_samples_layout = QHBoxLayout()
        total_samples_label = QLabel("Total Samples:", parent=form_group)
        total_samples_label.setStyleSheet("font-weight: bold;")
        total_samples_layout.addWidget(total_samples_label)
        total_samples_layout.addWidget(self.total_samples_field)
        total_samples_layout.addStretch()
        group_layout.addLayout(total_samples_layout)

        date_created_layout = QHBoxLayout()
        date_created_label = QLabel("Date Created:", parent=form_group)
        date_created_label.setStyleSheet("font-weight: bold;")
        date_created_layout.addWidget(date_created_label)
        date_created_layout.addWidget(self.date_created_field)
        date_created_layout.addStretch()
        group_layout.addLayout(date_created_layout)

        form_layout.addWidget(form_group)

    def set_tag(self, tag: Tag | None) -> None:
        """Populate the form with *tag* or reset it for a new tag."""

        self.tag = tag

        if tag is None:
            self.log.debug("Preparing widget for new tag entry")
            self.set_header_text("New Tag")
            self.name_field.setText("")
            self.description_field.setPlainText("")
            self.total_samples_field.setText("0")
            self.date_created_field.setText("Will be set on save")
            self.set_delete_visible(False)
            default_index = self.scope_combo.findData(Tag.DEFAULT_SCOPE)
            self.scope_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        else:
            self.log.debug("Loading tag into editor: id=%s name=%s", tag.id, tag.name)
            self.set_header_text(f"Edit Tag: {tag.name}")
            self.name_field.setText(tag.name)
            self.description_field.setPlainText(tag.description)
            self.total_samples_field.setText(str(tag.total_samples))
            self.date_created_field.setText(tag.date_created.strftime("%Y-%m-%d %H:%M:%S"))
            self.set_delete_visible(True)
            index = self.scope_combo.findData(tag.scope)
            if index >= 0:
                self.scope_combo.setCurrentIndex(index)
            else:
                fallback = self.scope_combo.findData(Tag.DEFAULT_SCOPE)
                self.scope_combo.setCurrentIndex(fallback if fallback >= 0 else 0)

        self.validate_form()

    def validate_form(self) -> None:
        """Validate user input and toggle the save button/validation message."""

        name = self.name_field.text()
        description = self.description_field.toPlainText()

        errors: list[str] = []

        current_id = self.tag.id if self.tag else None
        errors.extend(
            validate_entity_name(
                dataset=self.dataset,
                name=name,
                current_entity_id=current_id,
                fetch_existing=Tag.get_by_name,
                min_length=2,
                max_length=100,
                duplicate_message="A tag with this name already exists",
            )
        )
        errors.extend(
            validate_description(
                description,
                min_length=5,
                max_length=2000,
                empty_message="Description is required",
                short_message="Description must be at least 5 characters",
                long_message="Description must be less than 2000 characters",
            )
        )

        scope_value = self.scope_combo.currentData()
        try:
            Tag.normalize_scope(scope_value)
        except ValueError as exc:
            errors.append(str(exc))

        self.set_validation_errors(errors)

    def handle_save(self) -> None:
        """Persist the current form data to the dataset."""

        if not self.dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

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
                self.tag.update(
                    self.dataset, name=name, description=description, scope=normalized_scope
                )

            self.dataset.session.flush()
            self.dataset.session.commit()
            if self.tag is not None:
                self.dataset.session.refresh(self.tag)

        except SQLAlchemyError as exc:
            self.log.exception("Failed to save tag", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save tag: {exc}")
            return

        QMessageBox.information(self, "Success", f"Tag '{self.tag.name}' saved successfully!")
        self.tag_saved.emit(self.tag)
        self.set_tag(self.tag)

    def handle_delete(self) -> None:
        """Delete the current tag from the dataset after confirmation."""

        if not self.tag or not self.tag.id:
            return

        if not self.dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

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
        except SQLAlchemyError as exc:
            self.log.exception("Failed to delete tag", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete tag: {exc}")
            return

        QMessageBox.information(self, "Success", "Tag deleted successfully!")
        if deleted_tag is not None:
            self.tag_deleted.emit(deleted_tag)
        self.set_tag(None)

    def handle_cancel(self) -> None:
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

    def save_tag(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_save`."""

        self.handle_save()

    def delete_tag(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_delete`."""

        self.handle_delete()

    def cancel_editing(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_cancel`."""

        self.handle_cancel()
