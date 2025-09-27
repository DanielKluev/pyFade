"""Material-styled widget that provides CRUD operations for export templates.

The :class:`WidgetExportTemplate` encapsulates all form controls required to
create, update, duplicate, and delete :class:`py_fade.dataset.export_template.ExportTemplate`
objects. It mirrors the UX vocabulary used by other editors in pyFADE while
adding a facet configuration table that lets authors scope exports by limit
type, ordering strategy, and optional logprob thresholds.
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_crud_form_base import CrudButtonStyles, CrudFormWidget

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


FacetRow = dict[str, Any]


class WidgetExportTemplate(CrudFormWidget):
    """Interactive editor that manages the lifecycle of an export template."""

    template_saved = pyqtSignal(object)
    template_deleted = pyqtSignal(object)
    template_copied = pyqtSignal(object)

    app: "pyFadeApp"
    dataset: DatasetDatabase
    template: ExportTemplate | None

    def __init__(
        self,
        parent: QWidget | None,
        app: "pyFadeApp",
        dataset: DatasetDatabase,
        template: ExportTemplate | None,
    ) -> None:
        self.log = logging.getLogger("WidgetExportTemplate")
        self.app = app
        self.dataset = dataset
        self.template = template
        self._available_facets: dict[int, Facet] = {}

        button_styles = CrudButtonStyles(
            save=(
                "QPushButton { background-color: #3949AB; color: white; padding: 8px 16px; }"
            ),
            cancel=(
                "QPushButton { background-color: #9E9E9E; color: white; padding: 8px 16px; }"
            ),
            delete=(
                "QPushButton { background-color: #D32F2F; color: white; padding: 8px 16px; }"
            ),
        )

        super().__init__(
            parent,
            header_icon="description",
            header_title="Export Template",
            header_color="#3949AB",
            button_styles=button_styles,
            minimum_size=(760, 560),
        )

        self.save_button.setText("Save Template")
        self.cancel_button.setText("Revert")
        self.delete_button.setText("Delete")

        self.copy_button = QPushButtonWithIcon("content_copy", "Duplicate", parent=self)
        self.copy_button.setStyleSheet(
            "QPushButton { background-color: #5C6BC0; color: white; padding: 8px 16px; }"
        )
        self.insert_button(1, self.copy_button)

        self.connect_signals()
        self.refresh_facets()
        self.populate_output_formats(self.training_combo.currentData())
        self.toggle_encryption_controls(False)
        self.set_template(template)

    # ------------------------------------------------------------------
    # UI lifecycle helpers
    # ------------------------------------------------------------------
    def build_form(self, form_layout: QVBoxLayout) -> None:
        """Build and arrange the widget hierarchy."""

        form_layout.setSpacing(14)

        info_group = QGroupBox("Template Details", parent=self)
        info_layout = QGridLayout(info_group)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setHorizontalSpacing(12)
        info_layout.setVerticalSpacing(10)

        name_label = QLabel("Name:", parent=info_group)
        name_label.setStyleSheet("font-weight: bold;")
        self.name_input = QLineEdit(parent=info_group)
        self.name_input.setPlaceholderText("Unique template name…")
        info_layout.addWidget(name_label, 0, 0)
        info_layout.addWidget(self.name_input, 0, 1)

        description_label = QLabel("Description:", parent=info_group)
        description_label.setStyleSheet("font-weight: bold;")
        self.description_input = QLineEdit(parent=info_group)
        self.description_input.setPlaceholderText("How will this export be used?")
        info_layout.addWidget(description_label, 1, 0)
        info_layout.addWidget(self.description_input, 1, 1)

        training_label = QLabel("Training Type:", parent=info_group)
        training_label.setStyleSheet("font-weight: bold;")
        self.training_combo = QComboBox(parent=info_group)
        for value in ExportTemplate.TRAINING_TYPES:
            label = "SFT" if value == "SFT" else "DPO"
            self.training_combo.addItem(label, value)
        info_layout.addWidget(training_label, 2, 0)
        info_layout.addWidget(self.training_combo, 2, 1)

        output_label = QLabel("Output Format:", parent=info_group)
        output_label.setStyleSheet("font-weight: bold;")
        self.output_combo = QComboBox(parent=info_group)
        info_layout.addWidget(output_label, 3, 0)
        info_layout.addWidget(self.output_combo, 3, 1)

        model_label = QLabel("Model Families:", parent=info_group)
        model_label.setStyleSheet("font-weight: bold;")
        self.model_list = QListWidget(parent=info_group)
        self.model_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.model_list.setFixedHeight(96)
        for family in ExportTemplate.SUPPORTED_MODEL_FAMILIES:
            item = QListWidgetItem(family)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.model_list.addItem(item)
        info_layout.addWidget(model_label, 4, 0)
        info_layout.addWidget(self.model_list, 4, 1)

        filename_label = QLabel("Filename Template:", parent=info_group)
        filename_label.setStyleSheet("font-weight: bold;")
        self.filename_input = QLineEdit(parent=info_group)
        self.filename_input.setPlaceholderText(ExportTemplate.DEFAULT_FILENAME_TEMPLATE)
        info_layout.addWidget(filename_label, 5, 0)
        info_layout.addWidget(self.filename_input, 5, 1)

        normalize_label = QLabel("Normalize Dialogue Style:", parent=info_group)
        normalize_label.setStyleSheet("font-weight: bold;")
        self.normalize_checkbox = QCheckBox("Apply chat-style formatting helpers", parent=info_group)
        info_layout.addWidget(normalize_label, 6, 0)
        info_layout.addWidget(self.normalize_checkbox, 6, 1)

        form_layout.addWidget(info_group)

        # Encryption ---------------------------------------------------------
        encryption_group = QGroupBox("Encryption", parent=self)
        encryption_layout = QGridLayout(encryption_group)
        encryption_layout.setContentsMargins(12, 12, 12, 12)
        encryption_layout.setHorizontalSpacing(12)

        self.encrypt_checkbox = QCheckBox("Encrypt exported files with SQLCipher", parent=encryption_group)
        encryption_layout.addWidget(self.encrypt_checkbox, 0, 0, 1, 2)

        password_label = QLabel("Password (optional):", parent=encryption_group)
        password_label.setStyleSheet("font-weight: bold;")
        self.password_input = QLineEdit(parent=encryption_group)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Leave blank to request during export…")
        encryption_layout.addWidget(password_label, 1, 0)
        encryption_layout.addWidget(self.password_input, 1, 1)

        form_layout.addWidget(encryption_group)

        # Facets -------------------------------------------------------------
        facets_group = QGroupBox("Facet Selection", parent=self)
        facets_layout = QVBoxLayout(facets_group)
        facets_layout.setContentsMargins(12, 12, 12, 12)
        facets_layout.setSpacing(10)

        selector_layout = QHBoxLayout()
        self.facet_selector = QComboBox(parent=facets_group)
        self.facet_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.add_facet_button = QPushButtonWithIcon("add", "Add Facet", parent=facets_group)
        selector_layout.addWidget(self.facet_selector)
        selector_layout.addWidget(self.add_facet_button)
        selector_layout.addStretch()
        facets_layout.addLayout(selector_layout)

        self.facets_table = QTableWidget(0, 7)
        self.facets_table.setAlternatingRowColors(True)
        self.facets_table.setHorizontalHeaderLabels(
            [
                "Facet",
                "Limit Type",
                "Limit Value",
                "Order",
                "Min Logprob",
                "Avg Logprob",
                "",
            ]
        )
        header = self.facets_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column in range(1, 7):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        vertical_header = self.facets_table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.facets_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.facets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        facets_layout.addWidget(self.facets_table)

        form_layout.addWidget(facets_group)

    def connect_signals(self) -> None:
        """Wire up state change handlers for the form controls."""

        self.name_input.textChanged.connect(self.validate_form)
        self.description_input.textChanged.connect(self.validate_form)
        self.training_combo.currentIndexChanged.connect(
            lambda _: self.populate_output_formats(self.training_combo.currentData())
        )
        self.training_combo.currentIndexChanged.connect(lambda _: self.validate_form())
        self.output_combo.currentIndexChanged.connect(lambda _: self.validate_form())
        self.filename_input.textChanged.connect(self.validate_form)
        self.normalize_checkbox.stateChanged.connect(lambda _: self.validate_form())
        self.encrypt_checkbox.stateChanged.connect(self.on_encryption_toggled)
        self.password_input.textChanged.connect(self.validate_form)
        self.add_facet_button.clicked.connect(self.add_selected_facet)
        self.model_list.itemChanged.connect(lambda _: self.validate_form())
        self.copy_button.clicked.connect(self.copy_template)

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------
    def refresh_facets(self) -> None:
        """Populate the facet selector from the dataset."""

        session = self.dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        facets = Facet.get_all(self.dataset)
        self._available_facets = {facet.id: facet for facet in facets}

        self.facet_selector.clear()
        for facet in facets:
            self.facet_selector.addItem(f"{facet.name} (#{facet.id})", facet.id)
        self.facet_selector.setEnabled(bool(facets))
        self.add_facet_button.setEnabled(bool(facets))

    # ------------------------------------------------------------------
    # Template state management
    # ------------------------------------------------------------------
    def set_template(self, template: ExportTemplate | None) -> None:
        """Bind *template* to the form and populate UI controls."""

        self.template = template

        if template is None:
            self.log.debug("Preparing export template widget for new entry")
            self.set_header_text("New Export Template")
            self.name_input.setText("")
            self.description_input.setText("")
            self.training_combo.setCurrentIndex(0)
            self.populate_output_formats(self.training_combo.currentData())
            self.set_output_format(self.output_combo.itemData(0))
            self._set_model_selection([ExportTemplate.SUPPORTED_MODEL_FAMILIES[0]])
            self.filename_input.setText(ExportTemplate.DEFAULT_FILENAME_TEMPLATE)
            self.normalize_checkbox.setChecked(False)
            self.encrypt_checkbox.setChecked(False)
            self.password_input.setText("")
            self.copy_button.setEnabled(False)
            self.set_delete_visible(False)
            self.clear_facets_table()
        else:
            self.log.debug("Loading export template id=%s", template.id)
            self.set_header_text(f"Edit Export Template: {template.name}")
            self.name_input.setText(template.name)
            self.description_input.setText(template.description)
            self.training_combo.setCurrentIndex(
                self.training_combo.findData(template.training_type)
            )
            self.populate_output_formats(template.training_type)
            self.set_output_format(template.output_format)
            models = template.model_family.split(",") if template.model_family else []
            default_models = list(ExportTemplate.SUPPORTED_MODEL_FAMILIES[:1])
            self._set_model_selection(models or default_models)
            self.filename_input.setText(template.filename_template)
            self.normalize_checkbox.setChecked(template.normalize_style)
            self.encrypt_checkbox.setChecked(template.encrypt)
            self.password_input.setText(template.encryption_password or "")
            self.copy_button.setEnabled(True)
            self.set_delete_visible(True)
            self.populate_facets_table(template.facets_json)

        self.toggle_encryption_controls(self.encrypt_checkbox.isChecked())
        self.validate_form()

    def clear_facets_table(self) -> None:
        """Remove all facet rows from the configuration table."""

        self.facets_table.setRowCount(0)

    def populate_facets_table(self, facets: list[FacetRow]) -> None:
        """Rebuild the facets table from ``facets`` configuration."""

        self.clear_facets_table()
        for facet_config in facets:
            facet_id = int(facet_config.get("facet_id", 0))
            facet = self._available_facets.get(facet_id)
            if not facet:
                self.log.warning("Skipping facet id=%s (not available)", facet_id)
                continue
            self._insert_facet_row(facet, facet_config)

    def populate_output_formats(self, training_type: str) -> None:
        """Refresh the output format options for *training_type*."""

        current_selection = self.output_combo.currentData()
        self.output_combo.blockSignals(True)
        self.output_combo.clear()
        format_options = ExportTemplate.OUTPUT_FORMATS.get(
            training_type, ()  # type: ignore[arg-type]
        )
        for option in format_options:
            self.output_combo.addItem(option, option)
        self.output_combo.blockSignals(False)
        if current_selection:
            self.set_output_format(current_selection)
        has_items = self.output_combo.count() > 0
        no_selection = self.output_combo.currentIndex() < 0
        if has_items and no_selection:
            self.output_combo.setCurrentIndex(0)

    def set_output_format(self, value: str | None) -> None:
        """Apply *value* to the output format combo box if present."""

        if value is None:
            return
        index = self.output_combo.findData(value)
        if index < 0:
            index = self.output_combo.findText(value, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.output_combo.setCurrentIndex(index)

    def toggle_encryption_controls(self, enabled: bool) -> None:
        """Enable or clear the password fields based on *enabled* value."""

        self.password_input.setEnabled(enabled)
        if not enabled:
            self.password_input.setText("")

    # ------------------------------------------------------------------
    # Facet table operations
    # ------------------------------------------------------------------
    def add_selected_facet(self) -> None:
        """Insert the facet picked from the selector into the configuration table."""

        if not self._available_facets:
            QMessageBox.information(self, "No Facets", "No facets are available in this dataset.")
            return
        facet_id = self.facet_selector.currentData()
        if facet_id is None:
            return
        if self._is_facet_present(facet_id):
            QMessageBox.information(
                self,
                "Facet Already Added",
                "This facet is already part of the export template.",
            )
            return
        facet = self._available_facets.get(int(facet_id))
        if not facet:
            QMessageBox.warning(self, "Facet Missing", "The selected facet no longer exists.")
            return
        self._insert_facet_row(facet, None)
        self.validate_form()

    def _insert_facet_row(self, facet: Facet, config: FacetRow | None) -> None:
        row = self.facets_table.rowCount()
        self.facets_table.insertRow(row)

        facet_item = QTableWidgetItem(f"{facet.name}")
        facet_item.setData(Qt.ItemDataRole.UserRole, facet.id)
        self.facets_table.setItem(row, 0, facet_item)

        # Limit type combo ---------------------------------------------------
        limit_combo = QComboBox()
        limit_combo.addItem("Max Samples", "count")
        limit_combo.addItem("Percentage", "percentage")
        limit_combo.currentIndexChanged.connect(partial(self._on_limit_type_changed, limit_combo))
        self.facets_table.setCellWidget(row, 1, limit_combo)

        # Limit value --------------------------------------------------------
        limit_spin = QDoubleSpinBox()
        limit_spin.setDecimals(0)
        limit_spin.setMinimum(1)
        limit_spin.setMaximum(100000)
        limit_spin.setValue(100)
        self.facets_table.setCellWidget(row, 2, limit_spin)

        # Order --------------------------------------------------------------
        order_combo = QComboBox()
        order_combo.addItem("Random", "random")
        order_combo.addItem("Newest first", "newest")
        order_combo.addItem("Oldest first", "oldest")
        self.facets_table.setCellWidget(row, 3, order_combo)

        # Min and avg logprob -----------------------------------------------
        min_spin = self._build_logprob_spin()
        avg_spin = self._build_logprob_spin()
        self.facets_table.setCellWidget(row, 4, min_spin)
        self.facets_table.setCellWidget(row, 5, avg_spin)

        # Remove button ------------------------------------------------------
        remove_button = QPushButtonWithIcon("delete", "")
        remove_button.setToolTip("Remove this facet from the export configuration")
        remove_button.clicked.connect(partial(self._remove_facet_by_button, remove_button))
        self.facets_table.setCellWidget(row, 6, remove_button)

        if config:
            self._apply_facet_row_config(row, config)

    def _build_logprob_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setRange(-1000.0, 100.0)
        spin.setSpecialValueText("None")
        spin.setValue(-1000.0)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        return spin

    def _apply_facet_row_config(self, row: int, config: FacetRow) -> None:
        limit_combo = self._widget_from_table(row, 1, QComboBox)
        limit_spin = self._widget_from_table(row, 2, QDoubleSpinBox)
        order_combo = self._widget_from_table(row, 3, QComboBox)
        min_spin = self._widget_from_table(row, 4, QDoubleSpinBox)
        avg_spin = self._widget_from_table(row, 5, QDoubleSpinBox)

        if limit_combo:
            index = limit_combo.findData(config.get("limit_type", "count"))
            limit_combo.setCurrentIndex(index if index >= 0 else 0)
        if limit_spin:
            limit_type = config.get("limit_type", "count")
            self._configure_limit_spin(limit_spin, str(limit_type))
            limit_spin.setValue(float(config.get("limit_value", 100)))
        if order_combo:
            index = order_combo.findData(config.get("order", "random"))
            order_combo.setCurrentIndex(index if index >= 0 else 0)
        if min_spin:
            self._set_logprob_spin_value(min_spin, config.get("min_logprob"))
        if avg_spin:
            self._set_logprob_spin_value(avg_spin, config.get("avg_logprob"))

    def _set_logprob_spin_value(self, spin: QDoubleSpinBox, value: Any) -> None:
        if value in (None, ""):
            spin.setValue(spin.minimum())
        else:
            spin.setValue(float(value))

    def _is_facet_present(self, facet_id: int) -> bool:
        for row in range(self.facets_table.rowCount()):
            item = self.facets_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == facet_id:
                return True
        return False

    def _widget_from_table(self, row: int, column: int, widget_type: type[Any]) -> Any:
        widget = self.facets_table.cellWidget(row, column)
        if isinstance(widget, widget_type):
            return widget
        return None

    def _remove_facet_by_button(self, button: QPushButton) -> None:
        for row in range(self.facets_table.rowCount()):
            if self.facets_table.cellWidget(row, 6) is button:
                self.facets_table.removeRow(row)
                break
        self.validate_form()

    def _on_limit_type_changed(self, combo: QComboBox) -> None:
        row = self._find_row_for_widget(combo)
        if row is None:
            return
        limit_spin = self._widget_from_table(row, 2, QDoubleSpinBox)
        if not limit_spin:
            return
        limit_type = combo.currentData()
        self._configure_limit_spin(limit_spin, str(limit_type))
        self.validate_form()

    def _configure_limit_spin(self, spin: QDoubleSpinBox, limit_type: str) -> None:
        if limit_type == "percentage":
            spin.setDecimals(1)
            spin.setMinimum(1.0)
            spin.setMaximum(100.0)
            if spin.value() > 100.0 or spin.value() < 1.0:
                spin.setValue(50.0)
        else:
            spin.setDecimals(0)
            spin.setMinimum(1)
            spin.setMaximum(100000)
            if spin.value() < 1:
                spin.setValue(100)

    def _find_row_for_widget(self, widget: QWidget) -> int | None:
        for row in range(self.facets_table.rowCount()):
            for column in range(self.facets_table.columnCount()):
                if self.facets_table.cellWidget(row, column) is widget:
                    return row
        return None

    # ------------------------------------------------------------------
    # Validation and serialization
    # ------------------------------------------------------------------
    def validate_form(self) -> None:
        """Validate form state and toggle the save button accordingly."""

        errors: list[str] = []

        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        training_type = self.training_combo.currentData()
        output_format = self.output_combo.currentData()
        models = self._collect_selected_models()

        if not name:
            errors.append("Name is required.")
        elif len(name) < 3:
            errors.append("Name must be at least 3 characters long.")
        else:
            try:
                existing = ExportTemplate.get_by_name(self.dataset, name)
            except (RuntimeError, SQLAlchemyError) as exc:
                errors.append(str(exc))
            else:
                if existing and (
                    self.template is None or existing.id != getattr(self.template, "id", None)
                ):
                    errors.append("An export template with this name already exists.")

        if not description:
            errors.append("Description is required.")

        if not models:
            errors.append("Select at least one model family.")

        if training_type is None:
            errors.append("Training type is required.")
        if output_format is None:
            errors.append("Output format is required.")

        if self.facets_table.rowCount() == 0:
            errors.append("Add at least one facet to scope the export.")
        else:
            try:
                self._collect_facets_from_table()
            except ValueError as exc:
                errors.append(str(exc))

        self.set_validation_errors(errors)

    def _collect_selected_models(self) -> list[str]:
        """Return the list of model families currently checked in the UI."""

        models: list[str] = []
        for index in range(self.model_list.count()):
            item = self.model_list.item(index)
            if item and item.checkState() == Qt.CheckState.Checked:
                models.append(item.text())
        return models

    def _collect_facets_from_table(self) -> list[FacetRow]:
        """Convert the facets table rows into a serialisable list of dictionaries."""

        facets: list[FacetRow] = []
        for row in range(self.facets_table.rowCount()):
            item = self.facets_table.item(row, 0)
            if not item:
                raise ValueError("Facet table is missing row data.")
            facet_id = item.data(Qt.ItemDataRole.UserRole)
            if facet_id is None:
                raise ValueError("Facet row is missing an identifier.")

            limit_combo = self._widget_from_table(row, 1, QComboBox)
            limit_spin = self._widget_from_table(row, 2, QDoubleSpinBox)
            order_combo = self._widget_from_table(row, 3, QComboBox)
            min_spin = self._widget_from_table(row, 4, QDoubleSpinBox)
            avg_spin = self._widget_from_table(row, 5, QDoubleSpinBox)

            if not all([limit_combo, limit_spin, order_combo, min_spin, avg_spin]):
                raise ValueError("Facet row components are not fully initialized.")

            limit_type = limit_combo.currentData()
            limit_value = limit_spin.value()
            if limit_type == "percentage" and (limit_value <= 0 or limit_value > 100):
                raise ValueError("Facet percentage limit must be between 0 and 100.")
            if limit_type == "count" and limit_value < 1:
                raise ValueError("Facet max samples must be at least 1.")

            facets.append(
                {
                    "facet_id": int(facet_id),
                    "limit_type": str(limit_type),
                    "limit_value": limit_value,
                    "order": order_combo.currentData(),
                    "min_logprob": (
                        None if min_spin.value() == min_spin.minimum() else min_spin.value()
                    ),
                    "avg_logprob": (
                        None if avg_spin.value() == avg_spin.minimum() else avg_spin.value()
                    ),
                }
            )

        return facets

    def collect_form_data(self) -> dict[str, Any]:
        """Return a normalized representation of the form state."""

        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.text().strip(),
            "training_type": self.training_combo.currentData(),
            "output_format": self.output_combo.currentData(),
            "model_families": self._collect_selected_models(),
            "filename_template": self.filename_input.text().strip()
            or ExportTemplate.DEFAULT_FILENAME_TEMPLATE,
            "normalize_style": self.normalize_checkbox.isChecked(),
            "encrypt": self.encrypt_checkbox.isChecked(),
            "encryption_password": self.password_input.text().strip() or None,
            "facets": self._collect_facets_from_table(),
        }

    def _set_model_selection(self, models: list[str]) -> None:
        """Update the model list checkboxes to reflect ``models`` selection."""

        normalized_models = {model.strip().lower() for model in models if model}
        for index in range(self.model_list.count()):
            item = self.model_list.item(index)
            if not item:
                continue
            item.setCheckState(
                Qt.CheckState.Checked
                if item.text().strip().lower() in normalized_models
                else Qt.CheckState.Unchecked
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def handle_save(self) -> None:
        """Persist the form state to the dataset."""

        try:
            form_data = self.collect_form_data()
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid Data", str(exc))
            self.log.exception("Failed to collect form data", exc_info=exc)
            return

        session = self.dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        try:
            if self.template is None:
                self.log.debug("Creating export template with data: %s", form_data)
                self.template = ExportTemplate.create(self.dataset, **form_data)
            else:
                self.log.debug(
                    "Updating export template id=%s with %s",
                    self.template.id,
                    form_data,
                )
                self.template.update(self.dataset, **form_data)
            session.flush()
            session.commit()
            if self.template is not None:
                session.refresh(self.template)
        except (ValueError, RuntimeError, SQLAlchemyError) as exc:
            self.log.exception("Failed to save export template", exc_info=exc)
            session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save export template: {exc}")
            return

        QMessageBox.information(
            self, "Saved", f"Export template '{self.template.name}' saved successfully."
        )
        self.template_saved.emit(self.template)
        self.set_template(self.template)

    def handle_delete(self) -> None:
        """Delete the current export template after confirmation."""

        if self.template is None or not getattr(self.template, "id", None):
            return

        reply = QMessageBox.question(
            self,
            "Delete Export Template",
            f"Delete export template '{self.template.name}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        session = self.dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        try:
            template = self.template
            template.delete(self.dataset)
            session.commit()
        except (RuntimeError, SQLAlchemyError) as exc:
            self.log.exception("Failed to delete export template", exc_info=exc)
            session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete export template: {exc}")
            return

        QMessageBox.information(self, "Deleted", "Export template deleted successfully.")
        self.template_deleted.emit(template)
        self.set_template(None)

    def handle_cancel(self) -> None:
        """Revert the form to the last saved template state."""

        self.set_template(self.template)

    def save_template(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_save`."""

        self.handle_save()

    def delete_template(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_delete`."""

        self.handle_delete()

    def copy_template(self) -> None:
        """Duplicate the current template and emit :pyattr:`template_copied`."""

        if self.template is None:
            return

        session = self.dataset.session
        if session is None:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        try:
            new_template = self.template.duplicate(self.dataset)
            session.flush()
            session.commit()
            session.refresh(new_template)
        except (ValueError, RuntimeError, SQLAlchemyError) as exc:
            self.log.exception("Failed to duplicate export template", exc_info=exc)
            session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to duplicate export template: {exc}")
            return

        QMessageBox.information(
            self,
            "Duplicated",
            (
                f"A copy '{new_template.name}' has been created. "
                "It is now available in the navigation sidebar."
            ),
        )
        self.template_copied.emit(new_template)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------
    def on_encryption_toggled(self, state: int) -> None:
        """React to the encryption checkbox being toggled by the user."""

        enabled = state == Qt.CheckState.Checked
        self.toggle_encryption_controls(enabled)
        self.validate_form()
