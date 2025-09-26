import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.gui.components.widget_button_with_icon import QPushButtonWithIcon
from py_fade.gui.components.widget_label_with_icon import QLabelWithIcon

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetFacet(QWidget):
    """
    Widget to create, display, manage and edit a specific Facet item.
    Provides full CRUD functionality for Facet entities.
    """

    app: "pyFadeApp"
    dataset: "DatasetDatabase"
    facet: "Facet | None"

    # Signals
    facet_saved = pyqtSignal(object)  # Signal emitted when facet is saved
    facet_deleted = pyqtSignal(object)  # Signal emitted when facet is deleted
    facet_cancelled = pyqtSignal()  # Signal emitted when editing is cancelled

    def __init__(
        self,
        parent: QWidget | None,
        app: "pyFadeApp",
        dataset: "DatasetDatabase",
        facet: "Facet | None",
    ):
        super().__init__(parent)
        self.app = app
        self.dataset = dataset
        self.facet = facet

        self.setup_ui()
        self.set_facet(facet)

    def setup_ui(self):
        """Create and arrange UI components."""
        self.setMinimumSize(400, 300)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header section
        header_layout = QHBoxLayout()

        self.header_label = QLabelWithIcon("category", "Facet Details")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1976D2;")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Form section
        form_frame = QGroupBox("Facet Information")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(12)

        # Name field
        name_layout = QVBoxLayout()
        name_label = QLabel("Name:")
        name_label.setStyleSheet("font-weight: bold;")
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Enter facet name...")
        self.name_field.textChanged.connect(self.validate_form)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_field)
        form_layout.addLayout(name_layout)

        # Description field
        description_layout = QVBoxLayout()
        description_label = QLabel("Description:")
        description_label.setStyleSheet("font-weight: bold;")
        self.description_field = QPlainTextEdit()
        self.description_field.setPlaceholderText("Enter facet description...")
        self.description_field.setMaximumHeight(100)
        self.description_field.textChanged.connect(self.validate_form)
        description_layout.addWidget(description_label)
        description_layout.addWidget(self.description_field)
        form_layout.addLayout(description_layout)

        # Read-only fields for existing facets
        readonly_layout = QVBoxLayout()

        # Total samples field
        samples_layout = QHBoxLayout()
        samples_label = QLabel("Total Samples:")
        samples_label.setStyleSheet("font-weight: bold;")
        self.total_samples_field = QLineEdit()
        self.total_samples_field.setReadOnly(True)
        self.total_samples_field.setStyleSheet("background-color: #f5f5f5; color: #666;")
        samples_layout.addWidget(samples_label)
        samples_layout.addWidget(self.total_samples_field)
        samples_layout.addStretch()
        readonly_layout.addLayout(samples_layout)

        # Date created field
        date_layout = QHBoxLayout()
        date_label = QLabel("Date Created:")
        date_label.setStyleSheet("font-weight: bold;")
        self.date_created_field = QLineEdit()
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_created_field)
        date_layout.addStretch()
        readonly_layout.addLayout(date_layout)

        form_layout.addLayout(readonly_layout)

        main_layout.addWidget(form_frame)

        # Validation message
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.validation_label.setWordWrap(True)
        self.validation_label.hide()
        main_layout.addWidget(self.validation_label)

        main_layout.addStretch()

        # Button section
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.save_button = QPushButtonWithIcon("save", "Save")
        self.save_button.setStyleSheet(
            "QPushButton { background-color: #1976D2; color: white; padding: 8px 16px; }"
        )
        self.save_button.clicked.connect(self.save_facet)

        self.cancel_button = QPushButtonWithIcon("cancel", "Cancel")
        self.cancel_button.setStyleSheet(
            "QPushButton { background-color: #757575; color: white; padding: 8px 16px; }"
        )
        self.cancel_button.clicked.connect(self.cancel_editing)

        self.delete_button = QPushButtonWithIcon("delete", "Delete")
        self.delete_button.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; padding: 8px 16px; }"
        )
        self.delete_button.clicked.connect(self.delete_facet)

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)

        main_layout.addLayout(button_layout)

    def set_facet(self, facet: "Facet | None"):
        """Set the facet data and populate UI components."""
        self.facet = facet

        if facet is None:
            # New facet - clear all fields and show default values
            self.header_label.setText("New Facet")
            self.name_field.setText("")
            self.description_field.setPlainText("")
            self.total_samples_field.setText("0")
            self.date_created_field.setText("Will be set on save")
            self.delete_button.hide()
        else:
            # Existing facet - populate with current values
            self.header_label.setText(f"Edit Facet: {facet.name}")
            self.name_field.setText(facet.name)
            self.description_field.setPlainText(facet.description)
            self.total_samples_field.setText(str(facet.total_samples))
            self.date_created_field.setText(facet.date_created.strftime("%Y-%m-%d %H:%M:%S"))
            self.delete_button.show()

        self.validate_form()

    def validate_form(self):
        """Validate form inputs and update UI accordingly."""
        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()

        errors = []

        # Validate name
        if not name:
            errors.append("Name is required")
        elif len(name) < 2:
            errors.append("Name must be at least 2 characters")
        elif len(name) > 100:
            errors.append("Name must be less than 100 characters")
        else:
            # Check for duplicate names (excluding current facet if editing)
            existing_facet = Facet.get_by_name(self.dataset, name)
            if existing_facet and (not self.facet or existing_facet.id != self.facet.id):
                errors.append("A facet with this name already exists")

        # Validate description
        if not description:
            errors.append("Description is required")
        elif len(description) < 5:
            errors.append("Description must be at least 5 characters")
        elif len(description) > 1000:
            errors.append("Description must be less than 1000 characters")

        # Update validation display
        if errors:
            self.validation_label.setText("\n".join(errors))
            self.validation_label.show()
            self.save_button.setEnabled(False)
        else:
            self.validation_label.hide()
            self.save_button.setEnabled(True)

    def save_facet(self):
        """Save the current facet to the database."""
        if not self.dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()

        try:
            if self.facet is None:
                # Create new facet
                self.facet = Facet(
                    name=name,
                    description=description,
                    total_samples=0,
                    date_created=datetime.datetime.now(),
                )
                self.dataset.session.add(self.facet)
            else:
                # Update existing facet
                self.facet.name = name
                self.facet.description = description

            self.dataset.session.commit()

            # Show success message
            QMessageBox.information(
                self, "Success", f"Facet '{self.facet.name}' saved successfully!"
            )

            # Emit signal and refresh UI
            self.facet_saved.emit(self.facet)
            self.set_facet(self.facet)

        except Exception as e:
            self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save facet: {str(e)}")

    def delete_facet(self):
        """Delete the current facet from the database."""
        if not self.facet or not self.facet.id:
            return

        if not self.dataset.session:
            raise RuntimeError(
                "Dataset session is not initialized. Call dataset.initialize() first."
            )

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the facet '{self.facet.name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                facet_name = self.facet.name
                self.dataset.session.delete(self.facet)
                self.dataset.session.commit()

                # Show success message
                QMessageBox.information(
                    self, "Success", f"Facet '{facet_name}' deleted successfully!"
                )

                # Emit signal and clear UI
                self.facet_deleted.emit(self.facet)
                self.facet = None
                self.set_facet(None)

            except Exception as e:
                self.dataset.session.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete facet: {str(e)}")

    def cancel_editing(self):
        """Cancel the current editing operation."""
        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Are you sure you want to cancel? Any unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.facet_cancelled.emit()
            # Reset to original values
            self.set_facet(self.facet)
