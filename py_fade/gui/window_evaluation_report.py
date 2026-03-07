"""
Modal wizard that runs an export template in dry-run mode and shows per-sample issues.

Flow:
 1. Select export template.
 2. Configure issue-detection criteria.
 3. Select target model for logprob checks.
 4. Run evaluation (background thread).
 5. Review results and optionally save a YAML report.
"""

import logging
import pathlib
from typing import TYPE_CHECKING

import yaml
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
    QCheckBox,
    QSpinBox,
    QLineEdit,
)

from py_fade.gui.components.wizard_base import BaseWizard
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.controllers.evaluation_controller import EvaluationCriteria, EvaluationReport

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.controllers.evaluation_controller import EvaluationController


class EvaluationWorkerThread(QThread):
    """
    Background thread for running the evaluation without blocking the UI.
    """

    progress_updated = pyqtSignal(int, str)  # progress value (0-100), status message
    evaluation_completed = pyqtSignal(object)  # EvaluationReport
    evaluation_failed = pyqtSignal(str)  # error message

    def __init__(self, evaluation_controller: "EvaluationController"):
        """
        Initialise the worker with the configured evaluation controller.

        Args:
            evaluation_controller: Controller that will run the evaluation.
        """
        super().__init__()
        self.evaluation_controller = evaluation_controller
        self.log = logging.getLogger("EvaluationWorkerThread")

    def _progress_callback(self, current_facet_idx: int, total_facets: int, facet_name: str, current_sample: int,
                           total_samples: int) -> None:
        """
        Progress callback invoked by the evaluation controller.

        Calculates overall progress percentage and emits a status update.
        """
        current_sample = min(current_sample, total_samples)
        facet_progress = (current_sample / total_samples * 100) if total_samples > 0 else 0
        facet_weight = 100 / total_facets if total_facets > 0 else 100
        completed_facets_progress = (current_facet_idx - 1) * facet_weight
        current_facet_contribution = facet_progress * facet_weight / 100
        overall_progress = int(completed_facets_progress + current_facet_contribution)
        overall_progress = max(10, min(99, overall_progress))

        remaining_facets = total_facets - current_facet_idx
        status_parts = [f"Facet {current_facet_idx}/{total_facets}: {facet_name}", f"Sample {current_sample}/{total_samples}"]
        if remaining_facets > 0:
            status_parts.append(f"({remaining_facets} facet{'s' if remaining_facets > 1 else ''} remaining)")

        self.progress_updated.emit(overall_progress, " - ".join(status_parts))

    def run(self) -> None:
        """
        Execute the evaluation in the background thread.
        """
        try:
            self.progress_updated.emit(10, "Preparing evaluation...")
            self.evaluation_controller.progress_callback = self._progress_callback
            report = self.evaluation_controller.run_evaluation()
            self.progress_updated.emit(100, "Evaluation completed!")
            self.evaluation_completed.emit(report)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.log.error("Evaluation failed: %s", exc)
            self.evaluation_failed.emit(str(exc))


class EvaluationReportWizard(BaseWizard):
    """
    Step-by-step wizard for running an evaluation report against an export template.
    """

    STEP_TEMPLATE_SELECTION = 0
    STEP_CRITERIA_CONFIG = 1
    STEP_MODEL_SELECTION = 2
    STEP_RUNNING = 3
    STEP_RESULTS = 4

    def __init__(self, parent: "QWidget | None", app: "pyFadeApp", dataset: "DatasetDatabase"):
        """
        Initialise the wizard.

        Args:
            parent: Parent widget (can be None).
            app: Main application instance.
            dataset: Dataset to evaluate.
        """
        # Evaluation-specific attributes (must be set before super().__init__ calls setup_step_widgets).
        self.evaluation_controller: "EvaluationController | None" = None
        self.evaluation_worker: EvaluationWorkerThread | None = None

        self.selected_template: ExportTemplate | None = None
        self.selected_model_id: str | None = None
        self.evaluation_report: EvaluationReport | None = None

        # UI widget references (initialised to None to satisfy pylint).
        self.template_list: QListWidget | None = None
        self.template_details: QTextEdit | None = None
        # Criteria widgets
        self.check_export_failures_cb: QCheckBox | None = None
        self.high_rated_enabled_cb: QCheckBox | None = None
        self.high_rated_count_spin: QSpinBox | None = None
        self.high_rated_threshold_spin: QSpinBox | None = None
        self.regex_enabled_cb: QCheckBox | None = None
        self.regex_pattern_edit: QLineEdit | None = None
        self.regex_top_n_spin: QSpinBox | None = None
        # Model + progress + results
        self.model_combo: QComboBox | None = None
        self.progress_bar: QProgressBar | None = None
        self.progress_label: QLabel | None = None
        self.results_text: QTextEdit | None = None
        self.save_yaml_button: QPushButton | None = None

        super().__init__(parent, app, dataset, "Evaluation Report")

        self.load_templates()

    # ------------------------------------------------------------------
    # BaseWizard overrides
    # ------------------------------------------------------------------

    def setup_step_widgets(self) -> None:
        """
        Create and register all step widgets with the stacked widget.
        """
        self.content_stack.addWidget(self._create_template_selection_widget())
        self.content_stack.addWidget(self._create_criteria_config_widget())
        self.content_stack.addWidget(self._create_model_selection_widget())

        progress_widget = self.create_progress_widget(
            "Running evaluation against the selected template. Please wait...",
            "Ready to start evaluation...",
        )
        self.content_stack.addWidget(progress_widget)
        self.progress_bar = progress_widget.findChild(QProgressBar, "progress_bar")
        self.progress_label = progress_widget.findChild(QLabel, "progress_label")

        results_widget = self._create_results_widget()
        self.content_stack.addWidget(results_widget)

    def show_step(self, step: int) -> None:
        """
        Navigate to ``step`` and refresh button states.
        """
        self.content_stack.setCurrentIndex(step)
        self.back_button.setEnabled(step > 0)

        if step in (self.STEP_TEMPLATE_SELECTION, self.STEP_CRITERIA_CONFIG, self.STEP_MODEL_SELECTION):
            self.next_button.setText("Next →")
            self.update_next_button()
        elif step == self.STEP_RUNNING:
            self.next_button.setEnabled(False)
            self.back_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self._start_evaluation()
        elif step == self.STEP_RESULTS:
            self.next_button.setText("Close")
            self.next_button.setEnabled(True)
            self.back_button.setEnabled(False)
            self.cancel_button.setEnabled(False)

    def update_next_button(self) -> None:
        """
        Enable or disable the Next button depending on whether the current step is valid.
        """
        current_step = self.content_stack.currentIndex()
        if current_step == self.STEP_TEMPLATE_SELECTION:
            self.next_button.setEnabled(self.selected_template is not None)
        elif current_step == self.STEP_CRITERIA_CONFIG:
            self.next_button.setEnabled(True)
        elif current_step == self.STEP_MODEL_SELECTION:
            self.next_button.setEnabled(self.selected_model_id is not None)
        else:
            self.next_button.setEnabled(True)

    def go_next(self) -> None:
        """
        Advance to the next step or close the wizard on the final step.
        """
        current_step = self.content_stack.currentIndex()
        if current_step == self.STEP_RESULTS:
            self.accept()
            return
        if current_step < self.STEP_RESULTS:
            self.show_step(current_step + 1)

    # ------------------------------------------------------------------
    # Step widget builders
    # ------------------------------------------------------------------

    def _create_template_selection_widget(self) -> QWidget:
        """
        Build and return the template-selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        instructions = QLabel(
            "Select an export template to evaluate.  The template defines which facets and "
            "samples will be checked against the configured criteria.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        templates_group = QGroupBox("Available Export Templates", widget)
        templates_layout = QVBoxLayout(templates_group)

        self.template_list = QListWidget(widget)
        self.template_list.itemSelectionChanged.connect(self._on_template_selection_changed)
        templates_layout.addWidget(self.template_list)

        layout.addWidget(templates_group)

        details_group = QGroupBox("Template Details", widget)
        details_layout = QVBoxLayout(details_group)

        self.template_details = QTextEdit(widget)
        self.template_details.setReadOnly(True)
        self.template_details.setMaximumHeight(200)
        details_layout.addWidget(self.template_details)

        layout.addWidget(details_group)

        return widget

    def _create_criteria_config_widget(self) -> QWidget:
        """
        Build and return the criteria-configuration step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        instructions = QLabel(
            "Configure which issues to detect.  All enabled criteria will be checked for "
            "every sample in the selected template.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # --- Export failures ---
        export_group = QGroupBox("Standard Export Validation", widget)
        export_layout = QVBoxLayout(export_group)
        self.check_export_failures_cb = QCheckBox("Report samples that would fail standard export validation", widget)
        self.check_export_failures_cb.setChecked(True)
        export_layout.addWidget(self.check_export_failures_cb)
        layout.addWidget(export_group)

        # --- High-rated completions ---
        high_rated_group = QGroupBox("Completion Quality Check", widget)
        high_rated_layout = QVBoxLayout(high_rated_group)

        self.high_rated_enabled_cb = QCheckBox("Enable minimum high-rated completions check", widget)
        self.high_rated_enabled_cb.setChecked(False)
        self.high_rated_enabled_cb.toggled.connect(self._on_high_rated_toggled)
        high_rated_layout.addWidget(self.high_rated_enabled_cb)

        count_row = QHBoxLayout()
        count_label = QLabel("Minimum completions required:", widget)
        self.high_rated_count_spin = QSpinBox(widget)
        self.high_rated_count_spin.setMinimum(1)
        self.high_rated_count_spin.setMaximum(100)
        self.high_rated_count_spin.setValue(2)
        self.high_rated_count_spin.setEnabled(False)
        count_row.addWidget(count_label)
        count_row.addWidget(self.high_rated_count_spin)
        count_row.addStretch()
        high_rated_layout.addLayout(count_row)

        threshold_row = QHBoxLayout()
        threshold_label = QLabel("Minimum rating threshold (9 or 10):", widget)
        self.high_rated_threshold_spin = QSpinBox(widget)
        self.high_rated_threshold_spin.setMinimum(1)
        self.high_rated_threshold_spin.setMaximum(10)
        self.high_rated_threshold_spin.setValue(9)
        self.high_rated_threshold_spin.setEnabled(False)
        threshold_row.addWidget(threshold_label)
        threshold_row.addWidget(self.high_rated_threshold_spin)
        threshold_row.addStretch()
        high_rated_layout.addLayout(threshold_row)

        layout.addWidget(high_rated_group)

        # --- Completion regex ---
        regex_group = QGroupBox("Completion Content Check (regex)", widget)
        regex_layout = QVBoxLayout(regex_group)

        self.regex_enabled_cb = QCheckBox("Enable regex check on top-N completions", widget)
        self.regex_enabled_cb.setChecked(False)
        self.regex_enabled_cb.toggled.connect(self._on_regex_toggled)
        regex_layout.addWidget(self.regex_enabled_cb)

        regex_pattern_row = QHBoxLayout()
        regex_pattern_label = QLabel("Regex pattern (match = issue):", widget)
        self.regex_pattern_edit = QLineEdit(widget)
        self.regex_pattern_edit.setPlaceholderText("e.g. \\bI'm sorry\\b|I cannot")
        self.regex_pattern_edit.setEnabled(False)
        regex_pattern_row.addWidget(regex_pattern_label)
        regex_pattern_row.addWidget(self.regex_pattern_edit)
        regex_layout.addLayout(regex_pattern_row)

        top_n_row = QHBoxLayout()
        top_n_label = QLabel("Top N completions to check:", widget)
        self.regex_top_n_spin = QSpinBox(widget)
        self.regex_top_n_spin.setMinimum(1)
        self.regex_top_n_spin.setMaximum(50)
        self.regex_top_n_spin.setValue(3)
        self.regex_top_n_spin.setEnabled(False)
        top_n_row.addWidget(top_n_label)
        top_n_row.addWidget(self.regex_top_n_spin)
        top_n_row.addStretch()
        regex_layout.addLayout(top_n_row)

        layout.addWidget(regex_group)
        layout.addStretch()
        return widget

    def _create_model_selection_widget(self) -> QWidget:
        """
        Build and return the model-selection step widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        instructions = QLabel(
            "Select the target model for logprob threshold checks.  Only relevant when "
            "the 'Standard Export Validation' criterion is enabled.", widget)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        model_group = QGroupBox("Target Model", widget)
        model_layout = QVBoxLayout(model_group)

        model_label = QLabel("Choose the model to use for logprobs validation:", widget)
        model_layout.addWidget(model_label)

        self.model_combo = QComboBox(widget)
        self.model_combo.currentIndexChanged.connect(self._on_model_selection_changed)

        if hasattr(self.app, "providers_manager") and self.app.providers_manager.models:
            for model_id in self.app.providers_manager.models.keys():
                self.model_combo.addItem(model_id)

        model_layout.addWidget(self.model_combo)
        layout.addWidget(model_group)
        layout.addStretch()
        return widget

    def _create_results_widget(self) -> QWidget:
        """
        Build and return the results-display step widget (with save-YAML button).
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        summary_label = QLabel("Evaluation complete!", widget)
        summary_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(summary_label)

        self.results_text = QTextEdit(widget)
        self.results_text.setReadOnly(True)
        self.results_text.setObjectName("results_text")
        layout.addWidget(self.results_text)

        self.save_yaml_button = QPushButton("Save Report as YAML…", widget)
        self.save_yaml_button.clicked.connect(self._save_yaml_report)
        self.save_yaml_button.setEnabled(False)
        layout.addWidget(self.save_yaml_button)

        return widget

    # ------------------------------------------------------------------
    # Template loading
    # ------------------------------------------------------------------

    def load_templates(self) -> None:
        """
        Populate the template list from the dataset.
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

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to load templates: %s", exc)
            QMessageBox.critical(self, "Error", f"Failed to load export templates:\n{exc}")

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_template_selection_changed(self) -> None:
        """
        Update the selected template and refresh the details pane.
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
        self._update_template_details()
        self.update_next_button()

    def _update_template_details(self) -> None:
        """
        Render template metadata into the details text area.
        """
        if not self.selected_template:
            self.template_details.clear()
            return

        template = self.selected_template
        details = [
            f"<h3>{template.name}</h3>",
            f"<p><b>Description:</b> {template.description}</p>",
            f"<p><b>Training Type:</b> {template.training_type}</p>",
        ]

        if template.facets_json:
            details.append("<p><b>Facets:</b></p><ul>")
            for facet_config in template.facets_json:
                facet_id = facet_config.get("facet_id", "Unknown")
                facet = Facet.get_by_id(self.dataset, facet_id) if isinstance(facet_id, int) else None
                facet_label = facet.name if facet else f"Facet ID {facet_id}"
                limit_type = facet_config.get("limit_type", "count")
                limit_value = facet_config.get("limit_value", 100)
                suffix = "% of samples" if limit_type == "percentage" else " samples"
                details.append(f"<li>{facet_label}: {limit_value}{suffix}</li>")
            details.append("</ul>")

        self.template_details.setHtml("".join(details))

    def _on_high_rated_toggled(self, enabled: bool) -> None:
        """
        Enable or disable the high-rated count/threshold spin boxes.
        """
        self.high_rated_count_spin.setEnabled(enabled)
        self.high_rated_threshold_spin.setEnabled(enabled)

    def _on_regex_toggled(self, enabled: bool) -> None:
        """
        Enable or disable the regex pattern and top-N widgets.
        """
        self.regex_pattern_edit.setEnabled(enabled)
        self.regex_top_n_spin.setEnabled(enabled)

    def _on_model_selection_changed(self) -> None:
        """
        Update the selected model ID.
        """
        if self.model_combo and self.model_combo.count() > 0:
            self.selected_model_id = self.model_combo.currentText()
        else:
            self.selected_model_id = None
        self.update_next_button()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _build_criteria(self) -> EvaluationCriteria:
        """
        Construct an ``EvaluationCriteria`` from the current widget values.

        Returns:
            A fully configured ``EvaluationCriteria`` instance.
        """
        check_export = self.check_export_failures_cb.isChecked() if self.check_export_failures_cb else True

        high_rated_count = None
        if self.high_rated_enabled_cb and self.high_rated_enabled_cb.isChecked():
            high_rated_count = self.high_rated_count_spin.value() if self.high_rated_count_spin else 2
        high_rated_threshold = self.high_rated_threshold_spin.value() if self.high_rated_threshold_spin else 9

        completion_regex = None
        if self.regex_enabled_cb and self.regex_enabled_cb.isChecked():
            pattern = self.regex_pattern_edit.text().strip() if self.regex_pattern_edit else ""
            if pattern:
                completion_regex = pattern
        regex_top_n = self.regex_top_n_spin.value() if self.regex_top_n_spin else 3

        return EvaluationCriteria(
            check_export_failures=check_export,
            min_high_rated_completions=high_rated_count,
            min_high_rated_threshold=high_rated_threshold,
            completion_regex=completion_regex,
            completion_regex_top_n=regex_top_n,
        )

    def _stop_evaluation_worker(self) -> None:
        """
        Request interruption of the running evaluation worker and wait for it to finish.

        Safe to call even when no worker is running.
        """
        if self.evaluation_worker and self.evaluation_worker.isRunning():
            self.evaluation_worker.requestInterruption()
            self.evaluation_worker.wait(30000)

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """
        Stop the evaluation worker thread before closing the dialog.
        """
        self._stop_evaluation_worker()
        super().closeEvent(event)

    def reject(self) -> None:
        """
        Stop the evaluation worker thread before rejecting (Cancel / Esc).
        """
        self._stop_evaluation_worker()
        super().reject()

    def _start_evaluation(self) -> None:
        """
        Create the evaluation controller and start the background worker thread.
        """
        if not self.selected_template:
            self.log.error("Cannot start evaluation: no template selected")
            self._evaluation_failed("No template selected")
            return

        try:
            from py_fade.controllers.evaluation_controller import EvaluationController  # pylint: disable=import-outside-toplevel

            criteria = self._build_criteria()
            self.evaluation_controller = EvaluationController(
                self.app,
                self.dataset,
                self.selected_template,
                criteria=criteria,
                target_model_id=self.selected_model_id,
            )

            self.evaluation_worker = EvaluationWorkerThread(self.evaluation_controller)
            self.evaluation_worker.progress_updated.connect(self._update_progress)
            self.evaluation_worker.evaluation_completed.connect(self._evaluation_completed)
            self.evaluation_worker.evaluation_failed.connect(self._evaluation_failed)
            self.evaluation_worker.start()

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.log.error("Failed to start evaluation: %s", exc)
            self._evaluation_failed(str(exc))

    def _update_progress(self, progress: int, message: str) -> None:
        """
        Update the progress bar and status label.
        """
        if self.progress_bar:
            self.progress_bar.setValue(progress)
        if self.progress_label:
            self.progress_label.setText(message)

    def _evaluation_completed(self, report: EvaluationReport) -> None:
        """
        Handle successful evaluation completion.
        """
        self.evaluation_report = report
        self._update_results_display(success=True)
        self.show_step(self.STEP_RESULTS)

    def _evaluation_failed(self, error_message: str) -> None:
        """
        Handle evaluation failure.
        """
        self._update_results_display(success=False, error_message=error_message)
        self.show_step(self.STEP_RESULTS)

    # ------------------------------------------------------------------
    # Results display
    # ------------------------------------------------------------------

    def _update_results_display(self, success: bool, error_message: str = "") -> None:
        """
        Render evaluation results (or error) into the results text area.

        Args:
            success: Whether the evaluation completed without errors.
            error_message: Error description used when ``success`` is False.
        """
        if not self.results_text:
            return

        if not success:
            self.results_text.setHtml(f"<h3>Evaluation Failed</h3>"
                                      f"<p><b>Template:</b> {self.selected_template.name if self.selected_template else 'Unknown'}</p>"
                                      f"<p><b>Error:</b> {error_message}</p>"
                                      "<p>The evaluation could not complete. Please check the error and try again.</p>")
            return

        report = self.evaluation_report
        if not report:
            return

        html: list[str] = [
            f"<h3>Evaluation Report: {report.template_name}</h3>",
            f"<p><b>Total samples checked:</b> {report.total_samples_checked}</p>",
            f"<p><b>Samples with issues:</b> {report.total_samples_with_issues}</p>",
        ]

        if report.criteria_applied:
            html.append("<p><b>Criteria applied:</b></p><ul>")
            for criterion in report.criteria_applied:
                html.append(f"<li>{criterion}</li>")
            html.append("</ul>")

        if report.samples_with_issues:
            html.append("<hr><h4>Issues Found</h4>")
            for rec in report.samples_with_issues:
                display_name = f"{rec.group_path}/{rec.sample_title}" if rec.group_path else rec.sample_title
                html.append(f"<p><b>Sample:</b> {display_name} "
                            f"<i>(facet: {rec.facet_name}, id: {rec.sample_id})</i></p>"
                            "<ul>")
                for issue in rec.issues:
                    html.append(f"<li style='color:#d32f2f;'>[{issue.issue_type}] {issue.description}</li>")
                html.append("</ul>")
        else:
            html.append("<p style='color:#2e7d32;'><b>No issues found — all samples passed all active criteria.</b></p>")

        self.results_text.setHtml("".join(html))

        if self.save_yaml_button:
            self.save_yaml_button.setEnabled(True)

    # ------------------------------------------------------------------
    # YAML export
    # ------------------------------------------------------------------

    def _save_yaml_report(self) -> None:
        """
        Prompt the user for a save path and write the evaluation report as YAML.
        """
        if not self.evaluation_report:
            QMessageBox.warning(self, "No report", "No evaluation report is available to save.")
            return

        # Suggest a filename based on the template name.
        template_slug = self.evaluation_report.template_name.lower().replace(" ", "_")
        suggested_name = f"{template_slug}_evaluation_report.yaml"

        if self.app.config.last_report_path:
            default_dir = pathlib.Path(self.app.config.last_report_path)
            if not default_dir.exists() or not default_dir.is_dir():
                default_dir = pathlib.Path.home()
        else:
            default_dir = pathlib.Path.home()

        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Evaluation Report",
            str(default_dir / suggested_name),
            "YAML Files (*.yaml *.yml);;All Files (*.*)",
        )

        if not selected_path:
            return

        output_path = pathlib.Path(selected_path)
        if output_path.suffix.lower() not in (".yaml", ".yml"):
            output_path = output_path.with_suffix(".yaml")

        try:
            report_data = self._report_to_dict(self.evaluation_report)
            with open(output_path, "w", encoding="utf-8") as fh:
                yaml.dump(report_data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

            # Persist save directory.
            self.app.config.last_report_path = str(output_path.parent)
            self.app.config.save()

            QMessageBox.information(self, "Report saved", f"Evaluation report saved to:\n{output_path}")
        except (OSError, yaml.YAMLError) as exc:
            self.log.error("Failed to save YAML report: %s", exc)
            QMessageBox.critical(self, "Save failed", f"Could not save report:\n{exc}")

    @staticmethod
    def _report_to_dict(report: EvaluationReport) -> dict:
        """
        Convert an ``EvaluationReport`` to a plain-Python dictionary for YAML serialisation.

        Args:
            report: The report to serialise.

        Returns:
            A nested dictionary suitable for ``yaml.dump``.
        """
        samples_list = []
        for rec in report.samples_with_issues:
            samples_list.append({
                "sample_id": rec.sample_id,
                "sample_title": rec.sample_title,
                "group_path": rec.group_path,
                "facet_id": rec.facet_id,
                "facet_name": rec.facet_name,
                "issues": [{
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                } for issue in rec.issues],
            })

        return {
            "template_name": report.template_name,
            "total_samples_checked": report.total_samples_checked,
            "total_samples_with_issues": report.total_samples_with_issues,
            "criteria_applied": report.criteria_applied,
            "samples_with_issues": samples_list,
        }
