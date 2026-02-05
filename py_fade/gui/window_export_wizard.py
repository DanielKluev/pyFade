"""
Blocking (modal) window that guides user through exporting dataset to a file.

Flow:
 1. Select export template to use for the export.
 2. Select output file path and confirm export settings.
 3. Show export progress while running the export.
 4. Display export results summary.
"""

import logging
import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QProgressBar,
    QMessageBox,
    QGroupBox,
    QWidget,
    QComboBox,
)

from py_fade.gui.components.wizard_base import BaseWizard
from py_fade.dataset.export_template import ExportTemplate

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.controllers.export_controller import ExportController


class ExportWorkerThread(QThread):
    """
    Background thread for running export operations without blocking the UI.
    """
    progress_updated = pyqtSignal(int, str)  # progress value, status message
    export_completed = pyqtSignal(int)  # number of exported records
    export_failed = pyqtSignal(str)  # error message

    def __init__(self, export_controller: "ExportController"):
        super().__init__()
        self.export_controller = export_controller
        self.log = logging.getLogger("ExportWorkerThread")

    def _progress_callback(self, current_facet_idx: int, total_facets: int, facet_name: str, current_sample: int, total_samples: int):
        """
        Progress callback invoked by the export controller.

        Calculates overall progress percentage and emits progress updates with detailed status.
        """
        # Ensure current_sample doesn't exceed total_samples (defensive programming)
        current_sample = min(current_sample, total_samples)

        # Calculate progress within this facet (0-100)
        facet_progress = (current_sample / total_samples * 100) if total_samples > 0 else 0

        # Calculate overall progress across all facets
        # Each facet contributes (100 / total_facets)% to overall progress
        facet_weight = 100 / total_facets if total_facets > 0 else 100
        completed_facets_progress = (current_facet_idx - 1) * facet_weight
        current_facet_contribution = facet_progress * facet_weight / 100
        overall_progress = int(completed_facets_progress + current_facet_contribution)

        # Ensure progress is within bounds
        overall_progress = max(10, min(99, overall_progress))  # Keep between 10 and 99 during export

        # Create detailed status message
        remaining_facets = total_facets - current_facet_idx
        status_parts = [f"Facet {current_facet_idx}/{total_facets}: {facet_name}"]
        status_parts.append(f"Sample {current_sample}/{total_samples}")
        if remaining_facets > 0:
            status_parts.append(f"({remaining_facets} facet{'s' if remaining_facets > 1 else ''} remaining)")

        status_message = " - ".join(status_parts)

        self.progress_updated.emit(overall_progress, status_message)

    def run(self):
        """
        Execute the export operation in the background.
        """
        try:
            self.progress_updated.emit(10, "Preparing export...")

            # Set the progress callback on the controller
            self.export_controller.progress_callback = self._progress_callback

            # Run export
            exported_count = self.export_controller.run_export()

            self.progress_updated.emit(100, "Export completed successfully!")
            self.export_completed.emit(exported_count)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log.error("Export failed: %s", e)
            self.export_failed.emit(str(e))


class ExportWizard(BaseWizard):
    """
    Step-by-step wizard for exporting data from the dataset.
    """

    STEP_TEMPLATE_SELECTION = 0
    STEP_MODEL_SELECTION = 1
    STEP_OUTPUT_SELECTION = 2
    STEP_EXPORT_PROGRESS = 3
    STEP_RESULTS = 4

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase"):
        # Initialize export-specific attributes
        self.export_controller: "ExportController | None" = None
        self.export_worker: ExportWorkerThread | None = None

        self.selected_template: ExportTemplate | None = None
        self.selected_model_id: str | None = None
        self.output_path: pathlib.Path | None = None
        self.export_results: dict = {}

        # Initialize UI widget attributes to avoid pylint warnings
        self.template_list = None
        self.template_details = None
        self.model_combo = None
        self.output_path_input = None
        self.browse_button = None
        self.progress_bar = None
        self.progress_label = None
        self.results_text = None

        # Call parent constructor (this will call setup_step_widgets)
        super().__init__(parent, app, dataset, "Export Data Wizard")

        # Load templates after UI is set up
        self.load_templates()

    def setup_step_widgets(self):
        """
        Create widgets for each step of the wizard.
        """
        # Step 0: Template selection
        template_selection_widget = self.create_template_selection_widget()
        self.content_stack.addWidget(template_selection_widget)

        # Step 1: Model selection
        model_selection_widget = self.create_model_selection_widget()
        self.content_stack.addWidget(model_selection_widget)

        # Step 2: Output selection
        output_selection_widget = self.create_output_selection_widget()
        self.content_stack.addWidget(output_selection_widget)

        # Step 3: Export progress
        progress_widget = self.create_progress_widget("Exporting data using the selected template. Please wait...",
                                                      "Ready to start export...")
        self.content_stack.addWidget(progress_widget)

        # Get references to progress components
        self.progress_bar = progress_widget.findChild(QProgressBar, "progress_bar")
        self.progress_label = progress_widget.findChild(QLabel, "progress_label")

        # Step 4: Results
        results_widget = self.create_results_widget("Export completed!")
        self.content_stack.addWidget(results_widget)

        # Get reference to results text area
        self.results_text = results_widget.findChild(QTextEdit, "results_text")

    def create_template_selection_widget(self) -> QWidget:
        """
        Create the template selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Select an export template to use for the export operation. "\
                            "The template defines which samples to include and how to structure the output.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Template list
        templates_group = QGroupBox("Available Export Templates", widget)
        templates_layout = QVBoxLayout(templates_group)

        self.template_list = QListWidget(widget)
        self.template_list.itemSelectionChanged.connect(self.on_template_selection_changed)
        templates_layout.addWidget(self.template_list)

        layout.addWidget(templates_group)

        # Template details
        details_group = QGroupBox("Template Details", widget)
        details_layout = QVBoxLayout(details_group)

        self.template_details = QTextEdit(widget)
        self.template_details.setReadOnly(True)
        self.template_details.setMaximumHeight(200)
        details_layout.addWidget(self.template_details)

        layout.addWidget(details_group)

        return widget

    def create_model_selection_widget(self) -> QWidget:
        """
        Create the model selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Select the target model for logprobs validation. "\
                            "This model will be used to validate completion quality during export. "\
                            "Only completions with logprobs matching this model will be considered.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Model selection
        model_group = QGroupBox("Target Model", widget)
        model_layout = QVBoxLayout(model_group)

        model_label = QLabel("Choose the model to use for logprobs validation:", widget)
        model_layout.addWidget(model_label)

        self.model_combo = QComboBox(widget)
        self.model_combo.currentIndexChanged.connect(self.on_model_selection_changed)

        # Populate with available model IDs (not paths)
        if hasattr(self.app, 'providers_manager') and self.app.providers_manager.models:
            for model_id in self.app.providers_manager.models.keys():
                self.model_combo.addItem(model_id)

        model_layout.addWidget(self.model_combo)

        layout.addWidget(model_group)

        layout.addStretch()
        return widget

    def on_model_selection_changed(self):
        """
        Handle model selection change.
        """
        if self.model_combo and self.model_combo.count() > 0:
            self.selected_model_id = self.model_combo.currentText()
        else:
            self.selected_model_id = None
        self.update_next_button()

    def create_output_selection_widget(self) -> QWidget:
        """
        Create the output selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Choose where to save the exported file. "\
                            "The file format will be determined by the export template settings.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Output path selection
        path_group = QGroupBox("Output File", widget)
        path_layout = QVBoxLayout(path_group)

        path_input_layout = QHBoxLayout()
        self.output_path_input = QLabel("No file selected", widget)
        self.output_path_input.setStyleSheet("padding: 5px; border: 1px solid gray; background: #f0f0f0;")
        self.browse_button = QPushButton("Browse...", widget)
        self.browse_button.clicked.connect(self.browse_output_path)

        path_input_layout.addWidget(self.output_path_input)
        path_input_layout.addWidget(self.browse_button)
        path_layout.addLayout(path_input_layout)

        layout.addWidget(path_group)

        layout.addStretch()
        return widget

    def load_templates(self):
        """
        Load available export templates from the dataset.
        """
        if not self.dataset.session:
            self.log.warning("Dataset session not available, cannot load templates")
            return

        try:
            templates = self.dataset.session.query(ExportTemplate).all()
            self.template_list.clear()

            if not templates:
                item = QListWidgetItem("No export templates available")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.template_list.addItem(item)
                return

            for template in templates:
                item = QListWidgetItem(template.name)
                item.setData(Qt.ItemDataRole.UserRole, template)
                self.template_list.addItem(item)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to load templates: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to load export templates:\n{e}")

    def on_template_selection_changed(self):
        """
        Handle template selection change and update template details.
        """
        current_item = self.template_list.currentItem()
        if not current_item:
            self.selected_template = None
            self.template_details.clear()
            self.update_next_button()
            return

        template = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(template, ExportTemplate):
            self.selected_template = None
            self.template_details.clear()
            self.update_next_button()
            return

        self.selected_template = template
        self.update_template_details()
        self.update_next_button()

    def update_template_details(self):
        """
        Update the template details display with the selected template information.
        """
        if not self.selected_template:
            self.template_details.clear()
            return

        template = self.selected_template
        model_families_list = template.model_family.split(",") if template.model_family else []
        details = [
            f"<h3>{template.name}</h3>",
            f"<p><b>Description:</b> {template.description}</p>",
            f"<p><b>Training Type:</b> {template.training_type}</p>",
            f"<p><b>Output Format:</b> {template.output_format}</p>",
            f"<p><b>Model Families:</b> {', '.join(model_families_list) if model_families_list else 'None'}</p>",
        ]

        if template.facets_json:
            details.append("<p><b>Facets:</b></p><ul>")
            for facet_config in template.facets_json:
                facet_id = facet_config.get('facet_id', 'Unknown')
                limit_type = facet_config.get('limit_type', 'count')
                limit_value = facet_config.get('limit_value', 100)
                order = facet_config.get('order', 'random')

                facet_desc = f"Facet ID {facet_id}: {limit_value}"
                if limit_type == 'percentage':
                    facet_desc += "% of samples"
                else:
                    facet_desc += " samples"
                facet_desc += f" ({order} order)"

                # Add threshold info
                min_rating = facet_config.get('min_rating')
                if min_rating is not None:
                    facet_desc += f", min_rating={min_rating}"
                else:
                    facet_desc += ", min_rating=Default"

                min_logprob = facet_config.get('min_logprob')
                if min_logprob is not None:
                    facet_desc += f", min_logprob={min_logprob:.2f}"
                else:
                    facet_desc += ", min_logprob=Default"

                avg_logprob = facet_config.get('avg_logprob')
                if avg_logprob is not None:
                    facet_desc += f", avg_logprob={avg_logprob:.2f}"
                else:
                    facet_desc += ", avg_logprob=Default"

                details.append(f"<li>{facet_desc}</li>")
            details.append("</ul>")

        self.template_details.setHtml("".join(details))

    def browse_output_path(self):
        """
        Open a file dialog to select the output path.
        """
        if not self.selected_template:
            QMessageBox.warning(self, "No Template Selected", "Please select an export template first.")
            return

        # Suggest filename based on template
        suggested_name = f"{self.selected_template.name.lower().replace(' ', '_')}_export"

        # Add appropriate extension based on output format
        if self.selected_template.output_format == "JSONL-ShareGPT":
            suggested_name += ".jsonl"
        else:
            suggested_name += ".json"

        # Use last export path from config if available, otherwise use home directory
        if self.app.config.last_export_path:
            default_dir = pathlib.Path(self.app.config.last_export_path)
            # Verify directory still exists, fall back to home if not
            if not default_dir.exists() or not default_dir.is_dir():
                default_dir = pathlib.Path.home()
        else:
            default_dir = pathlib.Path.home()

        default_path = default_dir / suggested_name

        selected_path, _ = QFileDialog.getSaveFileName(self, "Select Export Output File", str(default_path),
                                                       "JSON Lines (*.jsonl);;JSON Files (*.json);;All Files (*.*)")

        if selected_path:
            self.output_path = pathlib.Path(selected_path)
            self.output_path_input.setText(str(self.output_path))
            self.update_next_button()

            # Save the directory to config for future use
            export_dir = self.output_path.parent
            self.app.config.last_export_path = str(export_dir)
            self.app.config.save()

    def show_step(self, step: int):
        """
        Show the specified step and update navigation buttons.
        """
        self.content_stack.setCurrentIndex(step)

        # Update button states
        self.back_button.setEnabled(step > 0)

        if step == self.STEP_TEMPLATE_SELECTION:
            self.next_button.setText("Next →")
            self.update_next_button()
        elif step == self.STEP_MODEL_SELECTION:
            self.next_button.setText("Next →")
            self.update_next_button()
        elif step == self.STEP_OUTPUT_SELECTION:
            self.next_button.setText("Export")
            self.update_next_button()
        elif step == self.STEP_EXPORT_PROGRESS:
            self.next_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self.start_export()
        elif step == self.STEP_RESULTS:
            self.next_button.setText("Close")
            self.next_button.setEnabled(True)
            self.back_button.setEnabled(False)
            self.cancel_button.setEnabled(False)

    def update_next_button(self):
        """
        Update the Next button state based on current step validation.
        """
        current_step = self.content_stack.currentIndex()

        if current_step == self.STEP_TEMPLATE_SELECTION:
            self.next_button.setEnabled(self.selected_template is not None)
        elif current_step == self.STEP_MODEL_SELECTION:
            self.next_button.setEnabled(self.selected_model_id is not None)
        elif current_step == self.STEP_OUTPUT_SELECTION:
            self.next_button.setEnabled(self.output_path is not None)
        else:
            self.next_button.setEnabled(True)

    def go_next(self):
        """
        Advance to the next step or close the wizard.
        """
        current_step = self.content_stack.currentIndex()

        if current_step == self.STEP_RESULTS:
            self.accept()
            return

        if current_step < self.STEP_RESULTS:
            self.show_step(current_step + 1)

    def start_export(self):
        """
        Start the export process in a background thread.
        """
        if not self.selected_template or not self.output_path:
            self.log.error("Cannot start export: missing template or output path")
            self.export_failed("Missing required information for export")
            return

        try:
            # Import here to avoid circular dependency
            from py_fade.controllers.export_controller import ExportController  # pylint: disable=import-outside-toplevel

            # Create export controller with selected target model
            self.export_controller = ExportController(self.app, self.dataset, self.selected_template, self.selected_model_id)
            self.export_controller.set_output_path(self.output_path)

            # Start export in background thread
            self.export_worker = ExportWorkerThread(self.export_controller)
            self.export_worker.progress_updated.connect(self.update_progress)
            self.export_worker.export_completed.connect(self.export_completed)
            self.export_worker.export_failed.connect(self.export_failed)
            self.export_worker.start()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to start export: %s", e)
            self.export_failed(str(e))

    def update_progress(self, progress: int, message: str):
        """
        Update the progress display during export.
        """
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def export_completed(self, exported_count: int):
        """
        Handle successful export completion.
        """
        self.export_results = {
            "success": True,
            "exported_count": exported_count,
            "output_path": self.output_path,
            "template_name": self.selected_template.name if self.selected_template else "Unknown",
            "detailed_results": self.export_controller.export_results if self.export_controller else None
        }

        self.update_results_display()
        self.show_step(self.STEP_RESULTS)

    def export_failed(self, error_message: str):
        """
        Handle export failure.
        """
        self.export_results = {
            "success": False,
            "error": error_message,
            "output_path": self.output_path,
            "template_name": self.selected_template.name if self.selected_template else "Unknown"
        }

        self.update_results_display()
        self.show_step(self.STEP_RESULTS)

    def _format_facet_summary_html(self, facet_summary) -> list[str]:
        """
        Format a single facet summary as HTML lines.

        Returns a list of HTML strings for the facet summary.
        """
        html_lines = [f"<hr><h4>Facet: {facet_summary.facet_name}</h4>"]

        # Exported samples
        if facet_summary.exported_samples:
            html_lines.append(f"<p><b>Exported Samples ({len(facet_summary.exported_samples)}):</b></p>")
            html_lines.append("<ul>")
            for sample_info in facet_summary.exported_samples:
                display_name = f"{sample_info.group_path or ''}/{sample_info.sample_title}"
                html_lines.append(f"<li>{display_name}</li>")
            html_lines.append("</ul>")
        else:
            html_lines.append("<p><i>No samples exported from this facet.</i></p>")

        # Failed samples
        if facet_summary.failed_samples:
            html_lines.append(f"<p><b>Failed Samples ({len(facet_summary.failed_samples)}):</b></p>")
            html_lines.append("<ul>")
            for sample_info, reasons in facet_summary.failed_samples:
                display_name = f"{sample_info.group_path or ''}/{sample_info.sample_title}"
                html_lines.append(f"<li>{display_name}")
                if reasons:
                    html_lines.append("<ul>")
                    for reason in reasons:
                        html_lines.append(f"<li style='color: #d32f2f;'>{reason}</li>")
                    html_lines.append("</ul>")
                html_lines.append("</li>")
            html_lines.append("</ul>")

        return html_lines

    def update_results_display(self):
        """
        Update the results display with export outcome.
        """
        if not self.export_results:
            return

        if self.export_results.get("success", False):
            results_html = [
                "<h3>Export Successful!</h3>",
                f"<p><b>Template:</b> {self.export_results.get('template_name', 'Unknown')}</p>",
                f"<p><b>Total Exported Samples:</b> {self.export_results.get('exported_count', 0)}</p>",
                f"<p><b>Output File:</b> {self.export_results.get('output_path', 'Unknown')}</p>",
            ]

            # Add detailed results if available
            detailed_results = self.export_results.get("detailed_results")
            if detailed_results:
                for facet_summary in detailed_results.facet_summaries:
                    results_html.extend(self._format_facet_summary_html(facet_summary))

            results_html.append(
                "<p>The export operation completed successfully. You can now use the exported file for your training or analysis tasks.</p>"
            )
        else:
            results_html = [
                "<h3>Export Failed</h3>", f"<p><b>Template:</b> {self.export_results.get('template_name', 'Unknown')}</p>",
                f"<p><b>Error:</b> {self.export_results.get('error', 'Unknown error')}</p>",
                "<p>The export operation failed. Please check the error message above and try again.</p>"
            ]

        self.results_text.setHtml("".join(results_html))
