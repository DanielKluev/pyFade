"""Widget for creating and editing dataset facets within the GUI."""

import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.exc import SQLAlchemyError

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.gui.components.widget_crud_form_base import CrudFormWidget, build_crud_button_styles

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp


class WidgetFacet(CrudFormWidget):
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
        self.app = app
        self.dataset = dataset
        self.facet = facet

        button_styles = build_crud_button_styles(save_color="#1976D2")

        super().__init__(
            parent,
            header_icon="category",
            header_title="Facet Details",
            header_color="#1976D2",
            button_styles=button_styles,
            minimum_size=(400, 300),
        )

        self.set_facet(facet)

    def build_form(self, form_layout: QVBoxLayout) -> None:
        """Create form controls specific to facet editing."""

        form_frame = QGroupBox("Facet Information", parent=self)
        frame_layout = QVBoxLayout(form_frame)
        frame_layout.setSpacing(12)

        name_layout = QVBoxLayout()
        name_label = QLabel("Name:", parent=form_frame)
        name_label.setStyleSheet("font-weight: bold;")
        self.name_field = QLineEdit(parent=form_frame)
        self.name_field.setPlaceholderText("Enter facet name...")
        self.name_field.textChanged.connect(self.validate_form)  # type: ignore[arg-type]
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_field)
        frame_layout.addLayout(name_layout)

        description_layout = QVBoxLayout()
        description_label = QLabel("Description:", parent=form_frame)
        description_label.setStyleSheet("font-weight: bold;")
        self.description_field = QPlainTextEdit(parent=form_frame)
        self.description_field.setPlaceholderText("Enter facet description...")
        self.description_field.setMaximumHeight(100)
        self.description_field.textChanged.connect(self.validate_form)  # type: ignore[arg-type]
        description_layout.addWidget(description_label)
        description_layout.addWidget(self.description_field)
        frame_layout.addLayout(description_layout)

        metadata_layout = QVBoxLayout()

        samples_layout = QHBoxLayout()
        samples_label = QLabel("Total Samples:", parent=form_frame)
        samples_label.setStyleSheet("font-weight: bold;")
        self.total_samples_field = QLineEdit(parent=form_frame)
        self.total_samples_field.setReadOnly(True)
        self.total_samples_field.setStyleSheet("background-color: #f5f5f5; color: #666;")
        samples_layout.addWidget(samples_label)
        samples_layout.addWidget(self.total_samples_field)
        samples_layout.addStretch()
        metadata_layout.addLayout(samples_layout)

        date_layout = QHBoxLayout()
        date_label = QLabel("Date Created:", parent=form_frame)
        date_label.setStyleSheet("font-weight: bold;")
        self.date_created_field = QLineEdit(parent=form_frame)
        self.date_created_field.setReadOnly(True)
        self.date_created_field.setStyleSheet("background-color: #f5f5f5; color: #666;")
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_created_field)
        date_layout.addStretch()
        metadata_layout.addLayout(date_layout)

        frame_layout.addLayout(metadata_layout)

        # Thresholds GroupBox
        thresholds_group = QGroupBox("Training Thresholds", parent=self)
        thresholds_layout = QVBoxLayout(thresholds_group)
        thresholds_layout.setSpacing(12)

        # Min Rating
        min_rating_layout = QHBoxLayout()
        min_rating_label = QLabel("Min Rating:", parent=thresholds_group)
        min_rating_label.setStyleSheet("font-weight: bold;")
        min_rating_label.setToolTip("Minimum rating for completion to be considered valid for training")
        self.min_rating_field = QSpinBox(parent=thresholds_group)
        self.min_rating_field.setRange(0, 10)
        self.min_rating_field.setValue(7)
        self.min_rating_field.setToolTip("Minimum rating (0-10) for completion to be considered valid")
        min_rating_layout.addWidget(min_rating_label)
        min_rating_layout.addWidget(self.min_rating_field)
        min_rating_layout.addStretch()
        thresholds_layout.addLayout(min_rating_layout)

        # Min Logprob Threshold
        min_logprob_layout = QHBoxLayout()
        min_logprob_label = QLabel("Min Logprob Threshold:", parent=thresholds_group)
        min_logprob_label.setStyleSheet("font-weight: bold;")
        min_logprob_label.setToolTip("Minimum logprob threshold for individual tokens")
        self.min_logprob_field = QDoubleSpinBox(parent=thresholds_group)
        self.min_logprob_field.setRange(-50.0, 0.0)
        self.min_logprob_field.setSingleStep(0.1)
        self.min_logprob_field.setDecimals(2)
        self.min_logprob_field.setValue(-1.0)
        self.min_logprob_field.setToolTip("Minimum logprob threshold for tokens (typically negative)")
        min_logprob_layout.addWidget(min_logprob_label)
        min_logprob_layout.addWidget(self.min_logprob_field)
        min_logprob_layout.addStretch()
        thresholds_layout.addLayout(min_logprob_layout)

        # Avg Logprob Threshold
        avg_logprob_layout = QHBoxLayout()
        avg_logprob_label = QLabel("Avg Logprob Threshold:", parent=thresholds_group)
        avg_logprob_label.setStyleSheet("font-weight: bold;")
        avg_logprob_label.setToolTip("Average logprob threshold for completions")
        self.avg_logprob_field = QDoubleSpinBox(parent=thresholds_group)
        self.avg_logprob_field.setRange(-15.0, 0.0)
        self.avg_logprob_field.setSingleStep(0.1)
        self.avg_logprob_field.setDecimals(2)
        self.avg_logprob_field.setValue(-0.4)
        self.avg_logprob_field.setToolTip("Average logprob threshold for completions (typically negative)")
        avg_logprob_layout.addWidget(avg_logprob_label)
        avg_logprob_layout.addWidget(self.avg_logprob_field)
        avg_logprob_layout.addStretch()
        thresholds_layout.addLayout(avg_logprob_layout)

        form_layout.addWidget(form_frame)
        form_layout.addWidget(thresholds_group)

    def set_facet(self, facet: "Facet | None") -> None:  # pylint: disable=duplicate-code
        """Set the facet data and populate UI components."""

        self.facet = facet

        if facet is None:
            self.set_header_text("New Facet")
            self.name_field.setText("")  # pylint: disable=duplicate-code
            self.description_field.setPlainText("")
            self.total_samples_field.setText("0")
            self.date_created_field.setText("Will be set on save")
            self.min_rating_field.setValue(7)
            self.min_logprob_field.setValue(-1.0)
            self.avg_logprob_field.setValue(-0.4)
            self.set_delete_visible(False)
        else:
            self.set_header_text(f"Edit Facet: {facet.name}")
            self.name_field.setText(facet.name)
            self.description_field.setPlainText(facet.description)
            self.total_samples_field.setText(str(facet.total_samples))
            self.date_created_field.setText(facet.date_created.strftime("%Y-%m-%d %H:%M:%S"))
            self.min_rating_field.setValue(facet.min_rating)
            self.min_logprob_field.setValue(facet.min_logprob_threshold)
            self.avg_logprob_field.setValue(facet.avg_logprob_threshold)
            self.set_delete_visible(True)

        self.validate_form()

    def validate_form(self) -> None:
        """
        Validate form inputs and update UI accordingly.
        """

        current_id = self.facet.id if self.facet else None
        name = self.name_field.text()
        description = self.description_field.toPlainText()

        errors: list[str] = []
        errors.extend(self.validate_name_unique(name, current_id, self.dataset, Facet))
        errors.extend(self.validate_description(description))
        self.set_validation_errors(errors)

    def handle_save(self) -> None:
        """Persist the current facet to the database."""

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        name = self.name_field.text().strip()
        description = self.description_field.toPlainText().strip()
        min_rating = self.min_rating_field.value()
        min_logprob_threshold = self.min_logprob_field.value()
        avg_logprob_threshold = self.avg_logprob_field.value()

        try:
            if self.facet is None:
                self.facet = Facet(
                    name=name,
                    description=description,
                    total_samples=0,
                    date_created=datetime.datetime.now(),
                    min_rating=min_rating,
                    min_logprob_threshold=min_logprob_threshold,
                    avg_logprob_threshold=avg_logprob_threshold,
                )
                self.dataset.session.add(self.facet)
            else:
                self.facet.name = name
                self.facet.description = description
                self.facet.min_rating = min_rating
                self.facet.min_logprob_threshold = min_logprob_threshold
                self.facet.avg_logprob_threshold = avg_logprob_threshold

            self.dataset.session.commit()
        except SQLAlchemyError as exc:
            self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save facet: {exc}")
            return

        QMessageBox.information(self, "Success", f"Facet '{self.facet.name}' saved successfully!")
        self.facet_saved.emit(self.facet)
        self.set_facet(self.facet)

    def handle_delete(self) -> None:
        """Delete the current facet from the dataset."""

        if not self.facet or not self.facet.id:
            return

        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the facet '{self.facet.name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            facet_name = self.facet.name
            self.dataset.session.delete(self.facet)
            self.dataset.session.commit()
        except SQLAlchemyError as exc:
            self.dataset.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete facet: {exc}")
            return

        QMessageBox.information(self, "Success", f"Facet '{facet_name}' deleted successfully!")
        self.facet_deleted.emit(self.facet)
        self.facet = None
        self.set_facet(None)

    def handle_cancel(self) -> None:
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
            self.set_facet(self.facet)

    def save_facet(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_save`."""

        self.handle_save()

    def delete_facet(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_delete`."""

        self.handle_delete()

    def cancel_editing(self) -> None:
        """Compatibility wrapper that delegates to :meth:`handle_cancel`."""

        self.handle_cancel()
