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
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.tag import Tag
from py_fade.gui.auxillary import create_description_field_layout, create_name_field_layout, create_readonly_field_layout
from py_fade.gui.components.widget_crud_form_base import CrudFormWidget, build_crud_button_styles

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

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: DatasetDatabase, tag: Tag | None) -> None:
        self.log = logging.getLogger("WidgetTag")
        self.app = app
        self.dataset = dataset
        self.dataset_session = self.initialize_dataset_session(dataset)
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

        # Name field
        name_container, self.name_field = create_name_field_layout(form_group, "Enter tag name…", self.validate_form)
        group_layout.addLayout(name_container)

        # Description field
        description_container, self.description_field = create_description_field_layout(form_group, "Describe how the tag should be used…",
                                                                                        120, self.validate_form)
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

        # Read-only fields
        self.total_samples_field = QLineEdit(parent=form_group)
        self.total_samples_field.setReadOnly(True)
        self.total_samples_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        self.date_created_field = QLineEdit(parent=form_group)
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        total_samples_layout = create_readonly_field_layout(form_group, "Total Samples:", self.total_samples_field)
        group_layout.addLayout(total_samples_layout)

        date_created_layout = create_readonly_field_layout(form_group, "Date Created:", self.date_created_field)
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
        """
        Validate user input and toggle the save button/validation message.
        """

        name = self.name_field.text()
        description = self.description_field.toPlainText()
        current_id = self.tag.id if self.tag else None
        errors: list[str] = []

        errors.extend(self.validate_name_unique(name, current_id, self.dataset, Tag))
        errors.extend(self.validate_description(description))

        scope_value = self.scope_combo.currentData()
        try:
            Tag.normalize_scope(scope_value)
        except ValueError as exc:
            errors.append(str(exc))

        self.set_validation_errors(errors)

    def handle_save(self) -> None:
        """
        Persist the current form data to the dataset.
        """

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

            self.dataset_session.flush()
            self.dataset_session.commit()
            if self.tag is not None:
                self.dataset_session.refresh(self.tag)

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
            self.dataset_session.commit()
        except SQLAlchemyError as exc:
            self.log.exception("Failed to delete tag", exc_info=exc)
            if self.dataset_session:
                self.dataset_session.rollback()
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
