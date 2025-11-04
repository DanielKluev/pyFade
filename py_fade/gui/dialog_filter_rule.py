"""Dialog for creating and editing filter rules.

Provides a user interface for selecting rule type, value, and negation setting.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.dataset.filter_rule import FilterRuleType
from py_fade.dataset.tag import Tag

if TYPE_CHECKING:
    pass


class DialogFilterRule(QDialog):
    """
    Dialog for creating or editing a single filter rule.

    Allows selecting rule type (String, Tag, Facet), value, and negation.
    """

    def __init__(self, parent: QWidget | None, dataset: DatasetDatabase, existing_rule: dict | None = None):
        super().__init__(parent)
        self.log = logging.getLogger("DialogFilterRule")
        self.dataset = dataset
        self.existing_rule = existing_rule

        self.setWindowTitle("Filter Rule")
        self.setMinimumWidth(400)

        self._setup_ui()
        self._load_rule(existing_rule)

    def _setup_ui(self) -> None:
        """
        Setup the dialog UI.
        """

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Rule type selection
        type_group = QGroupBox("Rule Type", self)
        type_layout = QFormLayout(type_group)

        self.type_combo = QComboBox(self)
        self.type_combo.addItem("String Search", FilterRuleType.STRING.value)
        self.type_combo.addItem("Tag", FilterRuleType.TAG.value)
        self.type_combo.addItem("Facet", FilterRuleType.FACET.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)  # type: ignore[arg-type]
        type_layout.addRow("Type:", self.type_combo)

        layout.addWidget(type_group)

        # Value selection group
        self.value_group = QGroupBox("Value", self)
        self.value_layout = QVBoxLayout(self.value_group)

        # String value input
        self.string_input = QLineEdit(self.value_group)
        self.string_input.setPlaceholderText("Enter search text...")
        self.value_layout.addWidget(self.string_input)

        # Tag selection combo
        self.tag_combo = QComboBox(self.value_group)
        self._populate_tags()
        self.value_layout.addWidget(self.tag_combo)

        # Facet selection combo
        self.facet_combo = QComboBox(self.value_group)
        self._populate_facets()
        self.value_layout.addWidget(self.facet_combo)

        layout.addWidget(self.value_group)

        # Negation checkbox
        self.negated_checkbox = QCheckBox("NOT (negate this rule)", self)
        self.negated_checkbox.setToolTip("When checked, matches samples that DON'T meet this criteria")
        layout.addWidget(self.negated_checkbox)

        # Help text
        help_label = QLabel(
            "Examples:\n"
            "• String: matches title, group path, or prompt text\n"
            "• Tag: matches samples with this tag\n"
            "• Facet: matches samples with ratings for this facet\n"
            "• NOT: reverses the match (e.g., 'NOT Tag Done' = samples without Done tag)", self)
        help_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 8px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.button_box.accepted.connect(self.accept)  # type: ignore[arg-type]
        self.button_box.rejected.connect(self.reject)  # type: ignore[arg-type]
        layout.addWidget(self.button_box)

        # Initial state
        self._on_type_changed()

    def _populate_tags(self) -> None:
        """
        Populate tag combo with available tags.
        """

        self.tag_combo.clear()
        tags = Tag.get_all(self.dataset, order_by_date=False)

        if not tags:
            self.tag_combo.addItem("(No tags available)", None)
            self.tag_combo.setEnabled(False)
            return

        self.tag_combo.setEnabled(True)
        for tag in tags:
            self.tag_combo.addItem(tag.name, tag.id)

    def _populate_facets(self) -> None:
        """
        Populate facet combo with available facets.
        """

        self.facet_combo.clear()
        facets = Facet.get_all(self.dataset, order_by_date=False)

        if not facets:
            self.facet_combo.addItem("(No facets available)", None)
            self.facet_combo.setEnabled(False)
            return

        self.facet_combo.setEnabled(True)
        for facet in facets:
            self.facet_combo.addItem(facet.name, facet.id)

    def _on_type_changed(self) -> None:
        """
        Show/hide appropriate value input based on selected rule type.
        """

        rule_type = self.type_combo.currentData()

        self.string_input.setVisible(rule_type == FilterRuleType.STRING.value)
        self.tag_combo.setVisible(rule_type == FilterRuleType.TAG.value)
        self.facet_combo.setVisible(rule_type == FilterRuleType.FACET.value)

    def _load_rule(self, rule_dict: dict | None) -> None:
        """
        Load existing rule into the dialog.
        """

        if not rule_dict:
            return

        rule_type = rule_dict.get("type", "")
        value = rule_dict.get("value")
        negated = rule_dict.get("negated", False)

        # Set rule type
        type_index = self.type_combo.findData(rule_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        # Set value based on type
        if rule_type == FilterRuleType.STRING.value:
            self.string_input.setText(str(value) if value else "")
        elif rule_type == FilterRuleType.TAG.value:
            tag_index = self.tag_combo.findData(value)
            if tag_index >= 0:
                self.tag_combo.setCurrentIndex(tag_index)
        elif rule_type == FilterRuleType.FACET.value:
            facet_index = self.facet_combo.findData(value)
            if facet_index >= 0:
                self.facet_combo.setCurrentIndex(facet_index)

        # Set negation
        self.negated_checkbox.setChecked(negated)

    def get_rule_dict(self) -> dict:
        """
        Get the rule as a dictionary.

        Returns:
            Dictionary with keys: type, value, negated
        """

        rule_type = self.type_combo.currentData()
        negated = self.negated_checkbox.isChecked()

        if rule_type == FilterRuleType.STRING.value:
            value = self.string_input.text().strip()
        elif rule_type == FilterRuleType.TAG.value:
            value = self.tag_combo.currentData()
        elif rule_type == FilterRuleType.FACET.value:
            value = self.facet_combo.currentData()
        else:
            value = ""

        return {"type": rule_type, "value": value, "negated": negated}
