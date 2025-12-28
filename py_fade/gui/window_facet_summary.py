"""Modal dialog for displaying facet summary report."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from py_fade.controllers.facet_summary_controller import FacetSummaryController, FacetSummaryReport
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.facet import Facet


class FacetSummaryWindow(QDialog):
    """
    Modal dialog showing facet summary report.

    Displays statistics about SFT and DPO readiness for samples in a facet,
    including detailed information about unfinished samples.
    """

    def __init__(self, app: "pyFadeApp", dataset: "DatasetDatabase", facet: "Facet", target_model: MappedModel, *,
                 parent: QWidget | None = None) -> None:
        """
        Initialize the facet summary window.

        Args:
            app: The main application instance
            dataset: Dataset database
            facet: Facet to generate report for
            target_model: Target model for logprob evaluation
            parent: Parent widget
        """
        super().__init__(parent)
        self.log = logging.getLogger(self.__class__.__name__)
        self.app = app
        self.dataset = dataset
        self.facet = facet
        self.target_model = target_model
        self.report: FacetSummaryReport | None = None

        self.setWindowTitle(f"Facet Summary: {facet.name}")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.generate_report()

    def setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_label = QLabel(f"<h2>Summary Report for Facet: {self.facet.name}</h2>")
        layout.addWidget(header_label)

        # Model info
        model_label = QLabel(f"<b>Target Model:</b> {self.target_model.model_id}")
        layout.addWidget(model_label)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setSpacing(15)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def generate_report(self) -> None:
        """Generate and display the facet summary report."""
        self.log.info("Generating facet summary report for facet '%s'", self.facet.name)

        # Generate report
        controller = FacetSummaryController(self.app, self.dataset, self.facet, self.target_model)
        self.report = controller.generate_report()

        # Display report
        self.display_report()

    def display_report(self) -> None:
        """Display the generated report in the UI."""
        if not self.report:
            return

        # Thresholds info
        thresholds_group = self.create_thresholds_section()
        self.content_layout.addWidget(thresholds_group)

        # SFT statistics
        sft_group = self.create_sft_section()
        self.content_layout.addWidget(sft_group)

        # DPO statistics
        dpo_group = self.create_dpo_section()
        self.content_layout.addWidget(dpo_group)

        # KTO statistics
        kto_group = self.create_kto_section()
        self.content_layout.addWidget(kto_group)

        # Add stretch at the end
        self.content_layout.addStretch()

    def create_thresholds_section(self) -> QGroupBox:
        """Create the thresholds information section."""
        if not self.report:
            raise RuntimeError("Report not generated yet.")
        group = QGroupBox("Training Thresholds")
        layout = QVBoxLayout(group)

        thresholds_text = f"""
        <b>Min Rating (Good):</b> {self.report.min_rating}<br>
        <b>Max Rating (Bad):</b> {self.report.max_rating}<br>
        <b>Min Logprob Threshold:</b> {self.report.min_logprob_threshold:.2f}<br>
        <b>Avg Logprob Threshold:</b> {self.report.avg_logprob_threshold:.2f}
        """
        label = QLabel(thresholds_text)
        layout.addWidget(label)

        return group

    def create_sft_section(self) -> QGroupBox:
        """Create the SFT statistics section."""
        if not self.report:
            raise RuntimeError("Report not generated yet.")
        group = QGroupBox("SFT (Supervised Fine-Tuning) Readiness")
        layout = QVBoxLayout(group)

        # Summary statistics
        summary_text = f"""
        <b>Total Samples:</b> {self.report.sft_total_samples}<br>
        <b>Finished Samples:</b> {self.report.sft_finished_samples} 
        ({self._percentage(self.report.sft_finished_samples, self.report.sft_total_samples)}%)<br>
        <b>Unfinished Samples:</b> {self.report.sft_unfinished_samples}<br>
        <b>Total Loss (finished):</b> {self.report.sft_total_loss:.4f}
        """
        summary_label = QLabel(summary_text)
        layout.addWidget(summary_label)

        # Unfinished samples details
        if self.report.sft_unfinished_details:
            layout.addWidget(QLabel("<b>Unfinished Samples:</b>"))
            for info in self.report.sft_unfinished_details[:20]:  # Limit to first 20
                sample_text = f"<b>• {info.sample_name}</b>"
                sample_label = QLabel(sample_text)
                layout.addWidget(sample_label)

                for reason in info.reasons:
                    reason_label = QLabel(f"  └─ {reason}")
                    reason_label.setStyleSheet("color: #666; font-size: 11px;")
                    layout.addWidget(reason_label)

            if len(self.report.sft_unfinished_details) > 20:
                more_label = QLabel(f"<i>... and {len(self.report.sft_unfinished_details) - 20} more</i>")
                more_label.setStyleSheet("color: #999;")
                layout.addWidget(more_label)

        return group

    def create_dpo_section(self) -> QGroupBox:
        """Create the DPO statistics section."""
        if not self.report:
            raise RuntimeError("Report not generated yet.")
        group = QGroupBox("DPO (Direct Preference Optimization) Readiness")
        layout = QVBoxLayout(group)

        # Summary statistics
        summary_text = f"""
        <b>Total Samples:</b> {self.report.dpo_total_samples}<br>
        <b>Finished Samples:</b> {self.report.dpo_finished_samples} 
        ({self._percentage(self.report.dpo_finished_samples, self.report.dpo_total_samples)}%)<br>
        <b>Unfinished Samples:</b> {self.report.dpo_unfinished_samples}<br>
        <b>Total Loss (finished):</b> {self.report.dpo_total_loss:.4f}
        """
        summary_label = QLabel(summary_text)
        layout.addWidget(summary_label)

        # Unfinished samples details
        if self.report.dpo_unfinished_details:
            layout.addWidget(QLabel("<b>Unfinished Samples:</b>"))
            for info in self.report.dpo_unfinished_details[:20]:  # Limit to first 20
                sample_text = f"<b>• {info.sample_name}</b>"
                sample_label = QLabel(sample_text)
                layout.addWidget(sample_label)

                for reason in info.reasons:
                    reason_label = QLabel(f"  └─ {reason}")
                    reason_label.setStyleSheet("color: #666; font-size: 11px;")
                    layout.addWidget(reason_label)

            if len(self.report.dpo_unfinished_details) > 20:
                more_label = QLabel(f"<i>... and {len(self.report.dpo_unfinished_details) - 20} more</i>")
                more_label.setStyleSheet("color: #999;")
                layout.addWidget(more_label)

        return group

    def create_kto_section(self) -> QGroupBox:
        """Create the KTO statistics section."""
        if not self.report:
            raise RuntimeError("Report not generated yet.")
        group = QGroupBox("KTO (Kahneman-Tversky Optimization) Readiness")
        layout = QVBoxLayout(group)

        # Summary statistics
        summary_text = f"""
        <b>Total Samples:</b> {self.report.kto_total_samples}<br>
        <b>Finished Samples:</b> {self.report.kto_finished_samples} 
        ({self._percentage(self.report.kto_finished_samples, self.report.kto_total_samples)}%)<br>
        <b>Unfinished Samples:</b> {self.report.kto_unfinished_samples}<br>
        <b>Good Samples (label=true):</b> {self.report.kto_good_samples}<br>
        <b>Bad Samples (label=false):</b> {self.report.kto_bad_samples}<br>
        <b>Total Loss (finished):</b> {self.report.kto_total_loss:.4f}
        """
        summary_label = QLabel(summary_text)
        layout.addWidget(summary_label)

        # Unfinished samples details
        if self.report.kto_unfinished_details:
            layout.addWidget(QLabel("<b>Unfinished Samples:</b>"))
            for info in self.report.kto_unfinished_details[:20]:  # Limit to first 20
                sample_text = f"<b>• {info.sample_name}</b>"
                sample_label = QLabel(sample_text)
                layout.addWidget(sample_label)

                for reason in info.reasons:
                    reason_label = QLabel(f"  └─ {reason}")
                    reason_label.setStyleSheet("color: #666; font-size: 11px;")
                    layout.addWidget(reason_label)

            if len(self.report.kto_unfinished_details) > 20:
                more_label = QLabel(f"<i>... and {len(self.report.kto_unfinished_details) - 20} more</i>")
                more_label.setStyleSheet("color: #999;")
                layout.addWidget(more_label)

        return group

    def _percentage(self, value: int, total: int) -> str:
        """Calculate percentage as a string, handling division by zero."""
        if total == 0:
            return "0.0"
        return f"{(value / total * 100):.1f}"
