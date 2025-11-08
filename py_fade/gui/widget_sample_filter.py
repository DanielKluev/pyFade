"""Interactive widget for authoring and managing sample filters.

Provides CRUD operations for complex sample filters with visual rule editing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.filter_rule import FilterRule
from py_fade.dataset.sample_filter import SampleFilter
from py_fade.gui.auxillary import create_description_field_layout, create_name_field_layout, create_readonly_field_layout
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_crud_form_base import CrudFormWidget, build_crud_button_styles

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetSampleFilter(CrudFormWidget):
    """
    Material-themed editor that provides CRUD operations for :class:`SampleFilter`.

    Allows creating, editing, and deleting complex sample filters with multiple rules.
    """

    sample_filter_saved = pyqtSignal(object)
    sample_filter_deleted = pyqtSignal(object)
    sample_filter_cancelled = pyqtSignal()

    app: "pyFadeApp"
    dataset: DatasetDatabase
    sample_filter: SampleFilter | None

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: DatasetDatabase, sample_filter: SampleFilter | None) -> None:
        self.log = logging.getLogger("WidgetSampleFilter")
        self.app = app
        self.dataset = dataset
        self.dataset_session = self.initialize_dataset_session(dataset)
        self.sample_filter = sample_filter
        self.current_rules: list[dict] = []

        button_styles = build_crud_button_styles(save_color="#9C27B0")

        super().__init__(
            parent,
            header_icon="filter_list",
            header_title="Sample Filter Details",
            header_color="#9C27B0",
            button_styles=button_styles,
            minimum_size=(500, 400),
        )

        self.set_sample_filter(sample_filter)

    def build_form(self, form_layout: QVBoxLayout) -> None:
        """
        Create all sample filter-specific input controls.
        """

        form_group = QGroupBox("Filter Information", parent=self)
        group_layout = QVBoxLayout(form_group)
        group_layout.setSpacing(12)

        # Name field
        name_container, self.name_field = create_name_field_layout(form_group, "Enter filter name…", self.validate_form)
        group_layout.addLayout(name_container)

        # Description field
        description_container, self.description_field = create_description_field_layout(form_group, "Describe what this filter finds…", 80,
                                                                                        self.validate_form)
        group_layout.addLayout(description_container)

        # Date created (read-only)
        self.date_created_field = QLineEdit(parent=form_group)
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")

        date_created_layout = create_readonly_field_layout(form_group, "Date Created:", self.date_created_field)
        group_layout.addLayout(date_created_layout)

        form_layout.addWidget(form_group)

        # Filter rules section
        rules_group = QGroupBox("Filter Rules (AND logic)", parent=self)
        rules_layout = QVBoxLayout(rules_group)
        rules_layout.setSpacing(8)

        # Rules list
        self.rules_list = QListWidget(parent=rules_group)
        self.rules_list.setMinimumHeight(150)
        rules_layout.addWidget(self.rules_list)

        # Rule management buttons
        rules_buttons_layout = QHBoxLayout()
        self.add_rule_button = QPushButtonWithIcon("add", "Add Rule", parent=rules_group)
        self.add_rule_button.clicked.connect(self._on_add_rule_clicked)  # type: ignore[arg-type]
        rules_buttons_layout.addWidget(self.add_rule_button)

        self.edit_rule_button = QPushButtonWithIcon("edit", "Edit Rule", parent=rules_group)
        self.edit_rule_button.clicked.connect(self._on_edit_rule_clicked)  # type: ignore[arg-type]
        self.edit_rule_button.setEnabled(False)
        rules_buttons_layout.addWidget(self.edit_rule_button)

        self.remove_rule_button = QPushButtonWithIcon("delete", "Remove Rule", parent=rules_group)
        self.remove_rule_button.clicked.connect(self._on_remove_rule_clicked)  # type: ignore[arg-type]
        self.remove_rule_button.setEnabled(False)
        rules_buttons_layout.addWidget(self.remove_rule_button)

        rules_buttons_layout.addStretch()
        rules_layout.addLayout(rules_buttons_layout)

        form_layout.addWidget(rules_group)

        # Connect list selection signal
        self.rules_list.itemSelectionChanged.connect(self._on_rule_selection_changed)  # type: ignore[arg-type]

    def set_sample_filter(self, sample_filter: SampleFilter | None) -> None:
        """
        Populate the form with *sample_filter* or reset it for a new filter.
        """

        self.sample_filter = sample_filter

        if sample_filter is None:
            self.log.debug("Preparing widget for new sample filter entry")
            self.set_header_text("New Sample Filter")
            self.name_field.setText("")
            self.description_field.setPlainText("")
            self.date_created_field.setText("Will be set on save")
            self.set_delete_visible(False)
            self.current_rules = []
        else:
            self.log.debug("Loading sample filter into editor: id=%s name=%s", sample_filter.id, sample_filter.name)
            self.set_header_text(f"Edit Filter: {sample_filter.name}")
            self.name_field.setText(sample_filter.name)
            self.description_field.setPlainText(sample_filter.description)
            self.date_created_field.setText(sample_filter.date_created.strftime("%Y-%m-%d %H:%M:%S"))
            self.set_delete_visible(True)
            self.current_rules = sample_filter.get_rules()

        self._refresh_rules_list()
        self.validate_form()

    def _refresh_rules_list(self) -> None:
        """
        Refresh the rules list display.
        """

        self.rules_list.clear()
        for rule_dict in self.current_rules:
            try:
                rule = FilterRule.from_dict(rule_dict)
                display_text = rule.get_display_text(self.dataset)
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, rule_dict)
                self.rules_list.addItem(item)
            except ValueError as e:
                self.log.warning("Invalid rule in filter: %s", e)
                continue

    def _on_rule_selection_changed(self) -> None:
        """
        Enable/disable rule editing buttons based on selection.
        """

        has_selection = len(self.rules_list.selectedItems()) > 0
        self.edit_rule_button.setEnabled(has_selection)
        self.remove_rule_button.setEnabled(has_selection)

    def _on_add_rule_clicked(self) -> None:
        """
        Open dialog to add a new filter rule.
        """

        rule_dict = self._show_rule_dialog(None)
        if rule_dict:
            self.current_rules.append(rule_dict)
            self._refresh_rules_list()
            self.validate_form()

    def _on_edit_rule_clicked(self) -> None:
        """
        Open dialog to edit the selected filter rule.
        """

        selected_items = self.rules_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        row = self.rules_list.row(item)
        current_rule = item.data(Qt.ItemDataRole.UserRole)

        rule_dict = self._show_rule_dialog(current_rule)
        if rule_dict:
            self.current_rules[row] = rule_dict
            self._refresh_rules_list()
            self.validate_form()

    def _on_remove_rule_clicked(self) -> None:
        """
        Remove the selected filter rule.
        """

        selected_items = self.rules_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        row = self.rules_list.row(item)

        reply = QMessageBox.question(self, "Confirm Removal", "Are you sure you want to remove this rule?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            del self.current_rules[row]
            self._refresh_rules_list()
            self.validate_form()

    def _show_rule_dialog(self, current_rule: dict | None) -> dict | None:
        """
        Show dialog for creating or editing a filter rule.

        Args:
            current_rule: Existing rule dict to edit, or None for new rule

        Returns:
            Rule dict if user saved, None if cancelled
        """

        from py_fade.gui.dialog_filter_rule import DialogFilterRule  # pylint: disable=import-outside-toplevel

        dialog = DialogFilterRule(self, self.dataset, current_rule)
        if dialog.exec() == 1:  # QDialog.Accepted
            return dialog.get_rule_dict()
        return None

    def validate_form(self) -> None:
        """
        Validate user input and toggle the save button/validation message.
        """

        name = self.name_field.text()
        description = self.description_field.toPlainText()
        current_id = self.sample_filter.id if self.sample_filter else None
        errors: list[str] = []

        errors.extend(self.validate_name_unique(name, current_id, self.dataset, SampleFilter))
        errors.extend(self.validate_description(description))

        self.set_validation_errors(errors)

    def handle_save(self) -> None:
        """
        Persist the current form data to the dataset.
        """

        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()

        try:
            if self.sample_filter is None:
                self.log.debug("Creating sample filter with name=%s", name)
                self.sample_filter = SampleFilter.create(self.dataset, name, description, filter_rules=self.current_rules)
            else:
                self.log.debug("Updating sample filter id=%s", self.sample_filter.id)
                self.sample_filter.update(self.dataset, name=name, description=description, filter_rules=self.current_rules)

            self.dataset_session.flush()
            self.dataset_session.commit()
            if self.sample_filter is not None:
                self.dataset_session.refresh(self.sample_filter)

        except SQLAlchemyError as exc:
            self.log.exception("Failed to save sample filter", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save filter: {exc}")
            return

        QMessageBox.information(self, "Success", f"Filter '{self.sample_filter.name}' saved successfully!")
        self.sample_filter_saved.emit(self.sample_filter)
        self.set_sample_filter(self.sample_filter)

    def handle_delete(self) -> None:
        """
        Delete the current sample filter from the dataset after confirmation.
        """

        if not self.sample_filter or not self.sample_filter.id:
            return

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the filter '{self.sample_filter.name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            self.log.debug("Deletion cancelled for sample filter id=%s", self.sample_filter.id)
            return

        try:
            filter_name = self.sample_filter.name
            self.sample_filter.delete(self.dataset)
            self.dataset_session.flush()
            self.dataset_session.commit()
            QMessageBox.information(self, "Success", f"Filter '{filter_name}' deleted successfully!")
            self.sample_filter_deleted.emit(self.sample_filter)
            self.sample_filter = None

        except SQLAlchemyError as exc:
            self.log.exception("Failed to delete sample filter", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete filter: {exc}")

    def handle_cancel(self) -> None:
        """
        Handle cancel action.
        """

        self.sample_filter_cancelled.emit()
