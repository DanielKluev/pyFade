"""
Modal dialog for switching, copying, or removing facets from a sample.

This module provides a dialog that allows users to:
- Remove a facet from a sample
- Change ratings/rankings from one facet to another
- Copy ratings/rankings from one facet to another
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet
    from py_fade.dataset.sample import Sample


class FacetSwitchDialog(QDialog):
    """
    Modal dialog for managing facet associations on a sample.

    Displays options to remove, change, or copy a facet's ratings and rankings.
    For change/copy operations, allows selecting a target facet.
    """

    ACTION_REMOVE = "remove"
    ACTION_CHANGE = "change"
    ACTION_COPY = "copy"

    def __init__(self, dataset: "DatasetDatabase", sample: "Sample", facet: "Facet", *, parent: QWidget | None = None) -> None:
        """
        Initialize the facet switch dialog.

        Args:
            dataset: Dataset database instance
            sample: Sample to manage facets for
            facet: The facet that was clicked (source facet)
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.dataset = dataset
        self.sample = sample
        self.source_facet = facet
        self.selected_action = None
        self.target_facet = None

        self.setWindowTitle(f"Facet Actions: {facet.name}")
        self.setMinimumSize(500, 300)
        self.setModal(True)

        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_label = QLabel(f"<h3>Facet Actions for '{self.source_facet.name}'</h3>")
        layout.addWidget(header_label)

        # Sample info
        sample_info = QLabel(f"<b>Sample:</b> {self.sample.title}")
        sample_info.setWordWrap(True)
        layout.addWidget(sample_info)

        # Facet info
        facet_info = QLabel(f"<b>Source Facet:</b> {self.source_facet.name}")
        facet_info.setWordWrap(True)
        layout.addWidget(facet_info)

        # Instructions
        instructions = QLabel("Select an action to perform on this facet:")
        layout.addWidget(instructions)

        # Action radio buttons
        self.action_group = QButtonGroup(self)

        self.remove_radio = QRadioButton("Remove this facet from the sample")
        self.remove_radio.setToolTip("Delete all ratings and rankings for this facet")
        self.action_group.addButton(self.remove_radio)
        layout.addWidget(self.remove_radio)

        self.change_radio = QRadioButton("Change to a different facet")
        self.change_radio.setToolTip("Move all ratings and rankings to another facet, then remove this facet")
        self.action_group.addButton(self.change_radio)
        layout.addWidget(self.change_radio)

        self.copy_radio = QRadioButton("Copy to a different facet")
        self.copy_radio.setToolTip("Duplicate all ratings and rankings to another facet, keeping this facet")
        self.action_group.addButton(self.copy_radio)
        layout.addWidget(self.copy_radio)

        # Target facet selection (for change/copy)
        target_label = QLabel("Target Facet (for Change/Copy):")
        layout.addWidget(target_label)

        self.target_combo = QComboBox()
        self.target_combo.setEnabled(False)
        layout.addWidget(self.target_combo)

        # Load available facets
        self._load_target_facets()

        # Connect radio button signals
        self.remove_radio.toggled.connect(self._on_action_changed)
        self.change_radio.toggled.connect(self._on_action_changed)
        self.copy_radio.toggled.connect(self._on_action_changed)

        # Info label for warnings
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.info_label)

        layout.addStretch()

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Set default selection
        self.remove_radio.setChecked(True)

    def _load_target_facets(self) -> None:
        """
        Load all available facets except the source facet into the combo box.
        """
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel

        all_facets = Facet.get_all(self.dataset, order_by_date=False)
        # Filter out the source facet and sort alphabetically
        available_facets = [f for f in all_facets if f.id != self.source_facet.id]
        available_facets.sort(key=lambda f: f.name.lower())

        if not available_facets:
            self.target_combo.addItem("<No other facets available>")
            self.change_radio.setEnabled(False)
            self.copy_radio.setEnabled(False)
        else:
            for facet in available_facets:
                self.target_combo.addItem(facet.name, facet.id)

    def _on_action_changed(self) -> None:
        """
        Handle action radio button changes.

        Enables/disables the target facet combo box based on selected action.
        """
        if self.remove_radio.isChecked():
            self.target_combo.setEnabled(False)
            self.info_label.setText("All ratings and rankings for this facet will be permanently deleted.")
        elif self.change_radio.isChecked():
            self.target_combo.setEnabled(True)
            self.info_label.setText("Ratings and rankings will be moved to the target facet. "
                                    "Existing ratings in the target facet will NOT be overwritten.")
        elif self.copy_radio.isChecked():
            self.target_combo.setEnabled(True)
            self.info_label.setText("Ratings and rankings will be copied to the target facet. "
                                    "Existing ratings in the target facet will NOT be overwritten.")

    def accept(self) -> None:
        """
        Apply the selected action and close the dialog.

        Validates the selection, performs the action using FacetSwitchController,
        and displays a summary of the results.
        """
        from py_fade.controllers.facet_switch_controller import FacetSwitchController  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel

        # Determine selected action
        if self.remove_radio.isChecked():
            self.selected_action = self.ACTION_REMOVE
        elif self.change_radio.isChecked():
            self.selected_action = self.ACTION_CHANGE
        elif self.copy_radio.isChecked():
            self.selected_action = self.ACTION_COPY
        else:
            QMessageBox.warning(self, "No Action Selected", "Please select an action to perform.")
            return

        # Get target facet if needed
        if self.selected_action in (self.ACTION_CHANGE, self.ACTION_COPY):
            if self.target_combo.currentIndex() < 0:
                QMessageBox.warning(self, "No Target Facet", "Please select a target facet.")
                return
            target_facet_id = self.target_combo.currentData()
            self.target_facet = Facet.get_by_id(self.dataset, target_facet_id)
            if not self.target_facet:
                QMessageBox.critical(self, "Error", "Selected target facet not found.")
                return

        try:
            controller = FacetSwitchController(self.dataset)

            if self.selected_action == self.ACTION_REMOVE:
                # Confirm removal
                confirm = QMessageBox.question(
                    self, "Confirm Removal", f"Are you sure you want to remove all ratings and rankings for facet "
                    f"'{self.source_facet.name}' from this sample?\n\nThis action cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if confirm != QMessageBox.StandardButton.Yes:
                    return

                count = controller.remove_facet_from_sample(self.sample, self.source_facet)
                QMessageBox.information(self, "Facet Removed", f"Removed {count} ratings/rankings for facet '{self.source_facet.name}'.")
                self.log.info("Removed facet '%s' from sample %d: %d items", self.source_facet.name, self.sample.id, count)

            elif self.selected_action == self.ACTION_CHANGE:
                transferred, skipped = controller.change_facet_for_sample(self.sample, self.source_facet, self.target_facet)
                message = f"Changed facet '{self.source_facet.name}' to '{self.target_facet.name}'.\n\n"
                message += f"Transferred: {transferred} ratings/rankings\n"
                if skipped > 0:
                    message += f"Skipped: {skipped} (already existed in target facet)"
                QMessageBox.information(self, "Facet Changed", message)
                self.log.info("Changed facet '%s' to '%s' for sample %d: transferred %d, skipped %d", self.source_facet.name,
                              self.target_facet.name, self.sample.id, transferred, skipped)

            elif self.selected_action == self.ACTION_COPY:
                copied, skipped = controller.copy_facet_for_sample(self.sample, self.source_facet, self.target_facet)
                message = f"Copied facet '{self.source_facet.name}' to '{self.target_facet.name}'.\n\n"
                message += f"Copied: {copied} ratings/rankings\n"
                if skipped > 0:
                    message += f"Skipped: {skipped} (already existed in target facet)"
                QMessageBox.information(self, "Facet Copied", message)
                self.log.info("Copied facet '%s' to '%s' for sample %d: copied %d, skipped %d", self.source_facet.name,
                              self.target_facet.name, self.sample.id, copied, skipped)

            super().accept()

        except (SQLAlchemyError, ValueError) as exc:
            self.log.exception("Failed to perform facet action", exc_info=exc)
            if self.dataset.session:
                self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to perform facet action: {exc}")
