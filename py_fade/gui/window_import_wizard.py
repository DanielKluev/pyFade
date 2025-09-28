"""
Blocking (modal) window that guides user through importing dataset from a file.

Important aspects:
 - Clearly establish completions source, is it human or model generated? Can we link to specific model_id?
 - Track origin of imported samples/completions (e.g. GSM8K, Anthropic HH dataset, etc).
 - Optionally, define target facet to assign to all imported samples/completions.
 - For benchmark evaluation results, support paired imports of logs, from base and tuned models to filter for regressions.
 - Filtering samples is essential, we don't want to import garbage data. Support filtering by:
    - Prompt text (substring match, regex)
    - Completion text (substring match, regex)
    - Evaluation result: pass/fail/new failure

Flow:
 1. Select file(s) to import from.
 2. Try to guess file format, if known format (e.g. JSONL with specific fields), parse it.
    If not, ask user to define format by mapping fields to known concepts (prompt, completion, model_id, evaluation result, etc).
 3. Preview samples/completions found in the file, with ability to filter out unwanted ones.
 4. Select source type (human/model/benchmark), model_id if applicable, and target facet if applicable.
 5. Define sample group paths to import into, creating new groups if needed.
 6. Confirm and run import, showing progress.
 7. Show summary of results.

TODO:
 - Start with implementing support of lm_eval benchmark JSONL files, with case of paired imports for base and tuned models.
 - For lm_eval, we expect JSON file with metadata, and JSONL file with individual samples. Paired by timestamp in the name.
 - Example files from lm_eval, for development and testing:
    - gemma3:12b-u1 (tuned), GSM8K 3 docs:
        `tests/data/results_2025-09-09T13-31-53.431753.json`
        `tests/data/samples_gsm8k_2025-09-09T13-31-53.431753.jsonl`
    - gemma3:12b-it-q4_K_M (base), GSM8K 3 docs:
        `tests/data/results_2025-09-09T13-42-42.857006.json`
        `tests/data/samples_gsm8k_2025-09-09T13-42-42.857006.jsonl`
    - Expected: 1 shared success, 1 shared failure, 1 new failure in tuned model.
  - Matching is done by `prompt_hash` field in the sample, which is SHA256 of the prompt text.
  - Comparison of results is done using fields defined in `metrics` field of the sample JSON object.
"""

import logging
import pathlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QProgressBar,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QScrollArea,
    QWidget,
)

from py_fade.controllers.import_controller import ImportController
from py_fade.dataset.facet import Facet

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


class ImportWorkerThread(QThread):
    """
    Background thread for running import operations without blocking the UI.
    """
    progress_updated = pyqtSignal(int, str)  # progress value, status message
    import_completed = pyqtSignal(int)  # number of imported records
    import_failed = pyqtSignal(str)  # error message

    def __init__(self, import_controller: ImportController):
        super().__init__()
        self.import_controller = import_controller
        self.log = logging.getLogger("ImportWorkerThread")

    def run(self):
        """
        Execute the import operation in the background.
        """
        try:
            self.progress_updated.emit(10, "Starting import...")

            # Load sources
            self.progress_updated.emit(30, "Loading data sources...")
            self.import_controller.load_sources()

            # Apply filters
            self.progress_updated.emit(50, "Applying filters...")
            self.import_controller.apply_filters()

            # Import to dataset
            self.progress_updated.emit(80, "Importing records to dataset...")
            imported_count = self.import_controller.import_to_dataset()

            self.progress_updated.emit(100, "Import completed successfully!")
            self.import_completed.emit(imported_count)

        except Exception as e:
            self.log.error("Import failed: %s", e)
            self.import_failed.emit(str(e))


class ImportWizard(QDialog):
    """
    Step-by-step wizard for importing data into the dataset.
    """

    STEP_FILE_SELECTION = 0
    STEP_FORMAT_DETECTION = 1
    STEP_PREVIEW_FILTER = 2
    STEP_CONFIGURATION = 3
    STEP_CONFIRMATION = 4
    STEP_IMPORT_PROGRESS = 5
    STEP_RESULTS = 6

    def __init__(self, parent: QWidget | None, app: "pyFadeApp", dataset: "DatasetDatabase"):
        super().__init__(parent)

        self.log = logging.getLogger("ImportWizard")
        self.app = app
        self.dataset = dataset
        self.import_controller = ImportController(app, dataset)
        self.import_worker: ImportWorkerThread | None = None

        self.selected_files: list[pathlib.Path] = []
        self.detected_formats: list[str] = []
        self.available_facets: list[Facet] = []

        self.setWindowTitle("Import Data Wizard")
        self.setModal(True)
        self.resize(800, 600)

        self.setup_ui()
        self.load_facets()
        self.show_step(self.STEP_FILE_SELECTION)

    def setup_ui(self):
        """
        Create and arrange the wizard UI components.
        """
        main_layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Import Data Wizard", self)
        header_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(header_label)

        # Step content area
        self.content_stack = QStackedWidget(self)
        main_layout.addWidget(self.content_stack)

        # Navigation buttons
        button_layout = QHBoxLayout()
        self.back_button = QPushButton("← Back", self)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)

        self.next_button = QPushButton("Next →", self)
        self.next_button.clicked.connect(self.go_next)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.next_button)

        main_layout.addLayout(button_layout)

        # Create all step widgets
        self.setup_step_widgets()

    def setup_step_widgets(self):
        """
        Create widgets for each step of the wizard.
        """
        # Step 0: File Selection
        self.file_selection_widget = self.create_file_selection_widget()
        self.content_stack.addWidget(self.file_selection_widget)

        # Step 1: Format Detection
        self.format_detection_widget = self.create_format_detection_widget()
        self.content_stack.addWidget(self.format_detection_widget)

        # Step 2: Preview & Filter
        self.preview_filter_widget = self.create_preview_filter_widget()
        self.content_stack.addWidget(self.preview_filter_widget)

        # Step 3: Configuration
        self.configuration_widget = self.create_configuration_widget()
        self.content_stack.addWidget(self.configuration_widget)

        # Step 4: Confirmation
        self.confirmation_widget = self.create_confirmation_widget()
        self.content_stack.addWidget(self.confirmation_widget)

        # Step 5: Import Progress
        self.progress_widget = self.create_progress_widget()
        self.content_stack.addWidget(self.progress_widget)

        # Step 6: Results
        self.results_widget = self.create_results_widget()
        self.content_stack.addWidget(self.results_widget)

    def create_file_selection_widget(self) -> QWidget:
        """
        Create the file selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel(
            "Select the data files you want to import. For lm-eval results, "
            "choose the results_*.json file (the corresponding samples file will be found automatically).", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File list
        file_group = QGroupBox("Selected Files", widget)
        file_group_layout = QVBoxLayout(file_group)

        self.file_list = QListWidget(file_group)
        file_group_layout.addWidget(self.file_list)

        # Buttons for adding/removing files
        file_button_layout = QHBoxLayout()
        self.add_file_button = QPushButton("Add Files...", file_group)
        self.add_file_button.clicked.connect(self.add_files)
        self.remove_file_button = QPushButton("Remove Selected", file_group)
        self.remove_file_button.clicked.connect(self.remove_selected_files)

        file_button_layout.addWidget(self.add_file_button)
        file_button_layout.addWidget(self.remove_file_button)
        file_button_layout.addStretch()

        file_group_layout.addLayout(file_button_layout)
        layout.addWidget(file_group)

        return widget

    def create_format_detection_widget(self) -> QWidget:
        """
        Create the format detection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("The wizard has detected the following file formats. "
                              "You can override the format selection if needed.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Format detection results
        self.format_table = QTableWidget(widget)
        self.format_table.setColumnCount(3)
        self.format_table.setHorizontalHeaderLabels(["File", "Detected Format", "Override"])
        self.format_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.format_table)

        return widget

    def create_preview_filter_widget(self) -> QWidget:
        """
        Create the preview and filtering step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Preview the data and apply filters to select which records to import.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Filter controls
        filter_group = QGroupBox("Filters", widget)
        filter_layout = QVBoxLayout(filter_group)

        # Paired comparison filter (for lm-eval)
        self.paired_filter_checkbox = QCheckBox("Enable paired comparison filter (for benchmark regression analysis)", filter_group)
        filter_layout.addWidget(self.paired_filter_checkbox)

        # Filter type selection
        filter_type_layout = QHBoxLayout()
        filter_type_layout.addWidget(QLabel("Filter type:", filter_group))
        self.filter_type_combo = QComboBox(filter_group)
        self.filter_type_combo.addItems(["new_failure", "shared_success", "shared_failure"])
        filter_type_layout.addWidget(self.filter_type_combo)
        filter_type_layout.addStretch()
        filter_layout.addLayout(filter_type_layout)

        layout.addWidget(filter_group)

        # Preview table
        preview_group = QGroupBox("Data Preview", widget)
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget(preview_group)
        preview_layout.addWidget(self.preview_table)

        self.record_count_label = QLabel("Total records: 0", preview_group)
        preview_layout.addWidget(self.record_count_label)

        layout.addWidget(preview_group)

        return widget

    def create_configuration_widget(self) -> QWidget:
        """
        Create the configuration step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Configure how the imported data should be processed and stored.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Facet selection
        facet_group = QGroupBox("Target Facet (Optional)", widget)
        facet_layout = QVBoxLayout(facet_group)

        self.facet_combo = QComboBox(facet_group)
        facet_layout.addWidget(self.facet_combo)

        facet_help = QLabel("Select a facet to assign ratings based on evaluation results. Leave empty to import without ratings.",
                            facet_group)
        facet_help.setWordWrap(True)
        facet_help.setStyleSheet("color: #666; font-size: 12px;")
        facet_layout.addWidget(facet_help)

        layout.addWidget(facet_group)

        # Rating configuration
        rating_group = QGroupBox("Rating Values", widget)
        rating_layout = QVBoxLayout(rating_group)

        rating_grid = QHBoxLayout()
        rating_grid.addWidget(QLabel("Correct:", rating_group))
        self.correct_rating_spin = QSpinBox(rating_group)
        self.correct_rating_spin.setRange(-10, 10)
        self.correct_rating_spin.setValue(8)
        rating_grid.addWidget(self.correct_rating_spin)

        rating_grid.addWidget(QLabel("Incorrect:", rating_group))
        self.incorrect_rating_spin = QSpinBox(rating_group)
        self.incorrect_rating_spin.setRange(-10, 10)
        self.incorrect_rating_spin.setValue(2)
        rating_grid.addWidget(self.incorrect_rating_spin)

        rating_grid.addStretch()
        rating_layout.addLayout(rating_grid)

        rating_grid2 = QHBoxLayout()
        rating_grid2.addWidget(QLabel("Chosen:", rating_group))
        self.chosen_rating_spin = QSpinBox(rating_group)
        self.chosen_rating_spin.setRange(-10, 10)
        self.chosen_rating_spin.setValue(8)
        rating_grid2.addWidget(self.chosen_rating_spin)

        rating_grid2.addWidget(QLabel("Rejected:", rating_group))
        self.rejected_rating_spin = QSpinBox(rating_group)
        self.rejected_rating_spin.setRange(-10, 10)
        self.rejected_rating_spin.setValue(2)
        rating_grid2.addWidget(self.rejected_rating_spin)

        rating_grid2.addStretch()
        rating_layout.addLayout(rating_grid2)

        layout.addWidget(rating_group)

        # Group path
        group_group = QGroupBox("Group Path (Optional)", widget)
        group_layout = QVBoxLayout(group_group)

        self.group_path_edit = QLineEdit(group_group)
        self.group_path_edit.setPlaceholderText("e.g., GSM8K/Math Problems")
        group_layout.addWidget(self.group_path_edit)

        group_help = QLabel("Specify a group path to organize imported samples. Leave empty to use auto-generated path.", group_group)
        group_help.setWordWrap(True)
        group_help.setStyleSheet("color: #666; font-size: 12px;")
        group_layout.addWidget(group_help)

        layout.addWidget(group_group)

        return widget

    def create_confirmation_widget(self) -> QWidget:
        """
        Create the confirmation step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Instructions
        instructions = QLabel("Review your import settings and click 'Start Import' to begin.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Summary display
        self.summary_text = QTextEdit(widget)
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(300)
        layout.addWidget(self.summary_text)

        return widget

    def create_progress_widget(self) -> QWidget:
        """
        Create the import progress step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Progress bar
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Status label
        self.progress_status_label = QLabel("Preparing import...", widget)
        layout.addWidget(self.progress_status_label)

        # Progress details
        self.progress_details = QTextEdit(widget)
        self.progress_details.setReadOnly(True)
        self.progress_details.setMaximumHeight(200)
        layout.addWidget(self.progress_details)

        return widget

    def create_results_widget(self) -> QWidget:
        """
        Create the results step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Results summary
        self.results_label = QLabel("Import completed!", widget)
        self.results_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.results_label)

        # Results details
        self.results_text = QTextEdit(widget)
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        return widget

    def load_facets(self):
        """
        Load available facets from the dataset.
        """
        self.available_facets = list(self.dataset.session.query(Facet).all())
        self.facet_combo.clear()
        self.facet_combo.addItem("(No facet)", None)
        for facet in self.available_facets:
            self.facet_combo.addItem(facet.name, facet)

    def show_step(self, step_index: int):
        """
        Show the specified step and update navigation buttons.
        """
        self.content_stack.setCurrentIndex(step_index)

        # Update button states
        self.back_button.setEnabled(step_index > self.STEP_FILE_SELECTION)

        if step_index == self.STEP_RESULTS:
            self.next_button.setText("Close")
            self.cancel_button.setVisible(False)
        elif step_index == self.STEP_IMPORT_PROGRESS:
            self.next_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.cancel_button.setText("Cancel Import")
        elif step_index == self.STEP_CONFIRMATION:
            self.next_button.setText("Start Import")
        else:
            self.next_button.setText("Next →")
            self.next_button.setEnabled(True)
            self.cancel_button.setText("Cancel")
            self.cancel_button.setVisible(True)

        # Update step-specific content
        if step_index == self.STEP_FORMAT_DETECTION:
            self.update_format_detection()
        elif step_index == self.STEP_PREVIEW_FILTER:
            self.update_preview()
        elif step_index == self.STEP_CONFIRMATION:
            self.update_confirmation()

    def go_back(self):
        """
        Navigate to the previous step.
        """
        current_step = self.content_stack.currentIndex()
        if current_step > self.STEP_FILE_SELECTION:
            self.show_step(current_step - 1)

    def go_next(self):
        """
        Navigate to the next step or execute the appropriate action.
        """
        current_step = self.content_stack.currentIndex()

        if current_step == self.STEP_FILE_SELECTION:
            if not self.validate_file_selection():
                return
            self.show_step(self.STEP_FORMAT_DETECTION)
        elif current_step == self.STEP_FORMAT_DETECTION:
            if not self.validate_format_detection():
                return
            self.show_step(self.STEP_PREVIEW_FILTER)
        elif current_step == self.STEP_PREVIEW_FILTER:
            if not self.validate_preview_filter():
                return
            self.show_step(self.STEP_CONFIGURATION)
        elif current_step == self.STEP_CONFIGURATION:
            if not self.validate_configuration():
                return
            self.show_step(self.STEP_CONFIRMATION)
        elif current_step == self.STEP_CONFIRMATION:
            self.start_import()
        elif current_step == self.STEP_RESULTS:
            self.accept()

    def add_files(self):
        """
        Open file dialog to add files for import.
        """
        files, _ = QFileDialog.getOpenFileNames(self, "Select Import Files", "",
                                                "JSON Files (*.json);;JSONL Files (*.jsonl);;All Files (*.*)")

        for file_path in files:
            path = pathlib.Path(file_path)
            if path not in self.selected_files:
                self.selected_files.append(path)
                item = QListWidgetItem(str(path.name))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.file_list.addItem(item)

    def remove_selected_files(self):
        """
        Remove selected files from the import list.
        """
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            item = self.file_list.takeItem(current_row)
            if item:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path in self.selected_files:
                    self.selected_files.remove(path)

    def validate_file_selection(self) -> bool:
        """
        Validate that at least one file is selected.
        """
        if not self.selected_files:
            QMessageBox.warning(self, "No Files Selected", "Please select at least one file to import.")
            return False
        return True

    def update_format_detection(self):
        """
        Update the format detection table.
        """
        self.format_table.setRowCount(len(self.selected_files))
        self.detected_formats = []

        for i, file_path in enumerate(self.selected_files):
            # Add file name
            self.format_table.setItem(i, 0, QTableWidgetItem(str(file_path.name)))

            # Detect format
            try:
                detected_format = self.import_controller.detect_format(file_path)
                if not detected_format:
                    detected_format = "unknown"
            except Exception as e:
                self.log.warning("Format detection failed for %s: %s", file_path, e)
                detected_format = "error"

            self.detected_formats.append(detected_format)
            self.format_table.setItem(i, 1, QTableWidgetItem(detected_format))

            # Add format override combo
            combo = QComboBox()
            combo.addItems(["lm_eval_results", "unknown"])
            combo.setCurrentText(detected_format if detected_format in ["lm_eval_results"] else "unknown")
            self.format_table.setCellWidget(i, 2, combo)

    def validate_format_detection(self) -> bool:
        """
        Validate format detection and add sources to import controller.
        """
        try:
            # Clear existing sources
            self.import_controller.sources = []

            for i, file_path in enumerate(self.selected_files):
                combo = self.format_table.cellWidget(i, 2)
                if combo:
                    format_override = combo.currentText()
                    if format_override == "unknown":
                        format_override = None

                    self.import_controller.add_source(file_path, format_override)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Format Error", f"Failed to process file formats:\n{str(e)}")
            return False

    def update_preview(self):
        """
        Update the preview table with loaded data.
        """
        try:
            # Load sources to get preview data
            self.import_controller.load_sources()

            # Update record count
            total_records = len(self.import_controller.active_records)
            self.record_count_label.setText(f"Total records: {total_records}")

            # Set up preview table
            if total_records > 0:
                sample_records = self.import_controller.active_records[:10]  # Show first 10 records
                self.preview_table.setRowCount(len(sample_records))
                self.preview_table.setColumnCount(4)
                self.preview_table.setHorizontalHeaderLabels(
                    ["Prompt (First 100 chars)", "Response (First 100 chars)", "Metrics", "Success"])

                for i, record in enumerate(sample_records):
                    # Truncate long text for display
                    prompt_preview = record.prompt_text[:100] + ("..." if len(record.prompt_text) > 100 else "")
                    response_preview = record.response_text[:100] + ("..." if len(record.response_text) > 100 else "")
                    metrics_str = str(record.metrics)
                    success_str = str(record.is_success())

                    self.preview_table.setItem(i, 0, QTableWidgetItem(prompt_preview))
                    self.preview_table.setItem(i, 1, QTableWidgetItem(response_preview))
                    self.preview_table.setItem(i, 2, QTableWidgetItem(metrics_str))
                    self.preview_table.setItem(i, 3, QTableWidgetItem(success_str))

                # Resize columns
                header = self.preview_table.horizontalHeader()
                if header:
                    header.setStretchLastSection(True)
                    for i in range(3):
                        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            else:
                self.preview_table.setRowCount(0)

        except Exception as e:
            QMessageBox.critical(self, "Preview Error", f"Failed to load preview data:\n{str(e)}")

    def validate_preview_filter(self) -> bool:
        """
        Validate preview and apply filters.
        """
        try:
            # Apply paired comparison filter if enabled
            if self.paired_filter_checkbox.isChecked():
                if len(self.import_controller.sources) != 2:
                    QMessageBox.warning(self, "Filter Error", "Paired comparison filter requires exactly 2 source files.")
                    return False

                filter_type = self.filter_type_combo.currentText()
                self.import_controller.add_filter("paired_comparison", {"filter_type": filter_type, "set_facet_pairwise_ranking": True})
                self.import_controller.apply_filters()

                # Update record count after filtering
                filtered_count = len(self.import_controller.active_records)
                self.record_count_label.setText(f"Total records: {filtered_count} (after filtering)")

            return True
        except Exception as e:
            QMessageBox.critical(self, "Filter Error", f"Failed to apply filters:\n{str(e)}")
            return False

    def validate_configuration(self) -> bool:
        """
        Validate and apply configuration settings.
        """
        try:
            # Set facet if selected
            facet_data = self.facet_combo.currentData()
            if facet_data:
                self.import_controller.set_facet(facet_data)

                # Set ratings
                self.import_controller.set_ratings(correct=self.correct_rating_spin.value(), incorrect=self.incorrect_rating_spin.value(),
                                                   chosen=self.chosen_rating_spin.value(), rejected=self.rejected_rating_spin.value())

            # Set group path if specified
            group_path = self.group_path_edit.text().strip()
            if group_path:
                self.import_controller.set_group_path(group_path)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", f"Failed to apply configuration:\n{str(e)}")
            return False

    def update_confirmation(self):
        """
        Update the confirmation summary.
        """
        summary_parts = []

        # Files
        summary_parts.append("FILES TO IMPORT:")
        for file_path in self.selected_files:
            summary_parts.append(f"  • {file_path.name}")

        summary_parts.append("")

        # Record count
        record_count = len(self.import_controller.active_records)
        summary_parts.append(f"TOTAL RECORDS: {record_count}")

        summary_parts.append("")

        # Configuration
        summary_parts.append("CONFIGURATION:")

        facet_data = self.facet_combo.currentData()
        if facet_data:
            summary_parts.append(f"  • Target Facet: {facet_data.name}")
            summary_parts.append(f"  • Ratings: Correct={self.correct_rating_spin.value()}, Incorrect={self.incorrect_rating_spin.value()}")
            summary_parts.append(f"  • Ratings: Chosen={self.chosen_rating_spin.value()}, Rejected={self.rejected_rating_spin.value()}")
        else:
            summary_parts.append("  • Target Facet: None (no ratings will be applied)")

        group_path = self.group_path_edit.text().strip()
        if group_path:
            summary_parts.append(f"  • Group Path: {group_path}")
        else:
            summary_parts.append("  • Group Path: Auto-generated")

        # Filters
        if self.import_controller.filters:
            summary_parts.append("")
            summary_parts.append("FILTERS:")
            for filter_config in self.import_controller.filters:
                filter_type = filter_config["type"]
                filter_details = filter_config["config"]
                summary_parts.append(f"  • {filter_type}: {filter_details}")

        self.summary_text.setPlainText("\n".join(summary_parts))

    def start_import(self):
        """
        Start the import operation.
        """
        self.show_step(self.STEP_IMPORT_PROGRESS)

        # Create and start the import worker thread
        self.import_worker = ImportWorkerThread(self.import_controller)
        self.import_worker.progress_updated.connect(self.update_progress)
        self.import_worker.import_completed.connect(self.import_completed)
        self.import_worker.import_failed.connect(self.import_failed)
        self.import_worker.start()

    def update_progress(self, progress: int, status: str):
        """
        Update the progress bar and status.
        """
        self.progress_bar.setValue(progress)
        self.progress_status_label.setText(status)
        self.progress_details.append(f"[{progress}%] {status}")

    def import_completed(self, imported_count: int):
        """
        Handle successful import completion.
        """
        self.log.info("Import completed successfully: %d records imported", imported_count)

        # Update results
        results_parts = [
            "Import completed successfully!",
            "",
            "RESULTS:",
            f"  • Records imported: {imported_count}",
            f"  • Samples created: {self.import_controller.import_summary.imported_samples}",
            f"  • Completions created: {self.import_controller.import_summary.imported_completions}",
        ]

        self.results_label.setText("✓ Import Completed Successfully!")
        self.results_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        self.results_text.setPlainText("\n".join(results_parts))

        self.show_step(self.STEP_RESULTS)

    def import_failed(self, error_message: str):
        """
        Handle import failure.
        """
        self.log.error("Import failed: %s", error_message)

        self.results_label.setText("✗ Import Failed")
        self.results_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        self.results_text.setPlainText(f"Import failed with error:\n\n{error_message}")

        self.show_step(self.STEP_RESULTS)
