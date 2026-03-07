"""
Tests for EvaluationReportWizard UI and EvaluationWorkerThread.

Validates:
- Wizard initialisation (title, modal, step widgets)
- Template list loading
- Criteria configuration widgets
- Navigation (Next/Back buttons)
- _build_criteria() collecting widget values
- YAML serialisation helper (_report_to_dict)
- Worker thread signals
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from py_fade.controllers.evaluation_controller import (
    EvaluationCriteria,
    EvaluationReport,
    IssueRecord,
    SampleIssueRecord,
)
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.gui.window_evaluation_report import EvaluationReportWizard, EvaluationWorkerThread

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_template(dataset: "DatasetDatabase", facet: Facet) -> ExportTemplate:
    """
    Create a minimal SFT export template pointing at *facet*.
    """
    template = ExportTemplate.create(
        dataset,
        name="UI Test Template",
        description="template for wizard tests",
        training_type="SFT",
        output_format="JSONL (ShareGPT)",
        model_families=["Gemma3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "percentage",
            "limit_value": 100,
            "order": "random",
        }],
    )
    dataset.commit()
    return template


# ---------------------------------------------------------------------------
# EvaluationReportWizard – initialisation
# ---------------------------------------------------------------------------


class TestEvaluationReportWizardInit:
    """
    Tests that the wizard starts in the correct state.
    """

    def test_window_title(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Wizard should have the expected window title.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.windowTitle() == "Evaluation Report"

    def test_is_modal(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Wizard should be modal.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.isModal()

    def test_initial_step_is_template_selection(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Wizard should start on the template selection step.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.content_stack.currentIndex() == EvaluationReportWizard.STEP_TEMPLATE_SELECTION

    def test_back_button_disabled_on_first_step(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Back button should be disabled on the first step.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert not wizard.back_button.isEnabled()

    def test_step_widgets_created(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        All required step widgets should be created and accessible.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.template_list is not None
        assert wizard.template_details is not None
        assert wizard.check_export_failures_cb is not None
        assert wizard.high_rated_enabled_cb is not None
        assert wizard.regex_enabled_cb is not None
        assert wizard.model_combo is not None
        assert wizard.progress_bar is not None
        assert wizard.progress_label is not None
        assert wizard.results_text is not None
        assert wizard.save_yaml_button is not None


# ---------------------------------------------------------------------------
# EvaluationReportWizard – template list
# ---------------------------------------------------------------------------


class TestEvaluationReportWizardTemplateList:
    """
    Tests for template-list loading and selection.
    """

    def test_no_templates_shows_placeholder(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        When no templates exist, a disabled placeholder item should appear.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.template_list.count() == 1
        item = wizard.template_list.item(0)
        assert "No export templates" in item.text()

    def test_templates_populate_list(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        When templates exist they should appear in the list.
        """
        facet = Facet.create(temp_dataset, "F1", "desc")
        temp_dataset.commit()
        _make_template(temp_dataset, facet)

        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.template_list.count() == 1
        assert wizard.template_list.item(0).text() == "UI Test Template"

    def test_selecting_template_enables_next(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Selecting a template should enable the Next button.
        """
        facet = Facet.create(temp_dataset, "F2", "desc")
        temp_dataset.commit()
        _make_template(temp_dataset, facet)

        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert not wizard.next_button.isEnabled()
        wizard.template_list.setCurrentRow(0)
        assert wizard.next_button.isEnabled()


# ---------------------------------------------------------------------------
# EvaluationReportWizard – criteria widgets
# ---------------------------------------------------------------------------


class TestEvaluationReportWizardCriteria:
    """
    Tests for criteria configuration widgets and _build_criteria().
    """

    def test_default_criteria_export_failures_checked(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Export-failures checkbox should be checked by default.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.check_export_failures_cb.isChecked()

    def test_high_rated_spinboxes_disabled_by_default(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        High-rated count/threshold spinboxes should be disabled until the checkbox is toggled.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert not wizard.high_rated_count_spin.isEnabled()
        assert not wizard.high_rated_threshold_spin.isEnabled()

    def test_high_rated_spinboxes_enabled_after_toggle(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Toggling the high-rated checkbox should enable the spinboxes.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.high_rated_enabled_cb.setChecked(True)

        assert wizard.high_rated_count_spin.isEnabled()
        assert wizard.high_rated_threshold_spin.isEnabled()

    def test_regex_widgets_disabled_by_default(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Regex pattern and top-N spinbox should be disabled until the checkbox is toggled.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert not wizard.regex_pattern_edit.isEnabled()
        assert not wizard.regex_top_n_spin.isEnabled()

    def test_regex_widgets_enabled_after_toggle(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Toggling the regex checkbox should enable the pattern edit and top-N spinbox.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.regex_enabled_cb.setChecked(True)

        assert wizard.regex_pattern_edit.isEnabled()
        assert wizard.regex_top_n_spin.isEnabled()

    def test_build_criteria_default_values(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        _build_criteria with default widget state returns expected EvaluationCriteria.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        criteria = wizard._build_criteria()  # pylint: disable=protected-access

        assert criteria.check_export_failures is True
        assert criteria.min_high_rated_completions is None
        assert criteria.completion_regex is None

    def test_build_criteria_with_high_rated_enabled(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        When high-rated checkbox is checked, _build_criteria captures spinbox values.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.high_rated_enabled_cb.setChecked(True)
        wizard.high_rated_count_spin.setValue(3)
        wizard.high_rated_threshold_spin.setValue(10)

        criteria = wizard._build_criteria()  # pylint: disable=protected-access

        assert criteria.min_high_rated_completions == 3
        assert criteria.min_high_rated_threshold == 10

    def test_build_criteria_with_regex_enabled(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        When regex checkbox is checked and a pattern is entered, _build_criteria captures it.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.regex_enabled_cb.setChecked(True)
        wizard.regex_pattern_edit.setText(r"\bsorry\b")
        wizard.regex_top_n_spin.setValue(5)

        criteria = wizard._build_criteria()  # pylint: disable=protected-access

        assert criteria.completion_regex == r"\bsorry\b"
        assert criteria.completion_regex_top_n == 5

    def test_build_criteria_empty_regex_treated_as_none(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        An empty regex pattern (after stripping) should result in completion_regex=None.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.regex_enabled_cb.setChecked(True)
        wizard.regex_pattern_edit.setText("   ")  # Whitespace only.

        criteria = wizard._build_criteria()  # pylint: disable=protected-access

        assert criteria.completion_regex is None


# ---------------------------------------------------------------------------
# EvaluationReportWizard – navigation
# ---------------------------------------------------------------------------


class TestEvaluationReportWizardNavigation:
    """
    Tests for step navigation.
    """

    def test_next_advances_step(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        go_next() should move to the criteria step after template selection.
        """
        facet = Facet.create(temp_dataset, "F3", "desc")
        temp_dataset.commit()
        _make_template(temp_dataset, facet)

        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.template_list.setCurrentRow(0)
        wizard.go_next()

        assert wizard.content_stack.currentIndex() == EvaluationReportWizard.STEP_CRITERIA_CONFIG

    def test_back_returns_to_previous_step(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        go_back() should decrement the current step.
        """
        facet = Facet.create(temp_dataset, "F4", "desc")
        temp_dataset.commit()
        _make_template(temp_dataset, facet)

        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.template_list.setCurrentRow(0)
        wizard.go_next()  # -> criteria
        assert wizard.content_stack.currentIndex() == EvaluationReportWizard.STEP_CRITERIA_CONFIG

        wizard.go_back()
        assert wizard.content_stack.currentIndex() == EvaluationReportWizard.STEP_TEMPLATE_SELECTION

    def test_back_button_disabled_on_step_zero(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Back button should be disabled when on step 0.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert wizard.content_stack.currentIndex() == 0
        assert not wizard.back_button.isEnabled()


# ---------------------------------------------------------------------------
# EvaluationReportWizard – results display and YAML report dict
# ---------------------------------------------------------------------------


class TestEvaluationReportWizardResults:
    """
    Tests for results rendering and YAML serialisation.
    """

    def test_update_results_display_success(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        _update_results_display with success=True should populate results_text.
        """
        facet = Facet.create(temp_dataset, "F5", "desc")
        temp_dataset.commit()
        _make_template(temp_dataset, facet)

        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.evaluation_report = EvaluationReport(
            template_name="T",
            total_samples_checked=5,
            samples_with_issues=[],
        )
        wizard._update_results_display(success=True)  # pylint: disable=protected-access

        html = wizard.results_text.toHtml()
        assert "5" in html  # total samples checked

    def test_update_results_display_failure(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        _update_results_display with success=False should show the error message.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)
        wizard.selected_template = MagicMock()
        wizard.selected_template.name = "My Template"

        wizard._update_results_display(success=False, error_message="Something went wrong")  # pylint: disable=protected-access

        html = wizard.results_text.toHtml()
        assert "Something went wrong" in html

    def test_save_yaml_button_disabled_initially(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Save YAML button should be disabled before a report is available.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        assert not wizard.save_yaml_button.isEnabled()

    def test_save_yaml_button_enabled_after_success(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Save YAML button should be enabled after a successful evaluation.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        wizard.evaluation_report = EvaluationReport(template_name="T", total_samples_checked=2)
        wizard._update_results_display(success=True)  # pylint: disable=protected-access

        assert wizard.save_yaml_button.isEnabled()

    def test_report_to_dict_structure(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        _report_to_dict should produce the expected dictionary structure.
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        report = EvaluationReport(
            template_name="My Template",
            total_samples_checked=3,
            samples_with_issues=[
                SampleIssueRecord(
                    sample_id=1,
                    sample_title="Sample A",
                    group_path="group/sub",
                    facet_id=10,
                    facet_name="Reasoning",
                    issues=[IssueRecord(issue_type="export_failure", description="No completions")],
                )
            ],
            criteria_applied=["Export failures"],
        )

        result = EvaluationReportWizard._report_to_dict(report)  # pylint: disable=protected-access

        assert result["template_name"] == "My Template"
        assert result["total_samples_checked"] == 3
        assert result["total_samples_with_issues"] == 1
        assert result["criteria_applied"] == ["Export failures"]
        assert len(result["samples_with_issues"]) == 1

        sample_entry = result["samples_with_issues"][0]
        assert sample_entry["sample_id"] == 1
        assert sample_entry["facet_name"] == "Reasoning"
        assert sample_entry["issues"][0]["issue_type"] == "export_failure"

    def test_report_to_dict_group_path_none(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        group_path=None should be preserved in the YAML dict (not coerced to a string).
        """
        wizard = EvaluationReportWizard(None, app_with_dataset, temp_dataset)
        qtbot.addWidget(wizard)

        report = EvaluationReport(
            template_name="T",
            samples_with_issues=[
                SampleIssueRecord(1, "S", None, 1, "F", [IssueRecord("t", "d")]),
            ],
        )
        result = EvaluationReportWizard._report_to_dict(report)  # pylint: disable=protected-access

        assert result["samples_with_issues"][0]["group_path"] is None


# ---------------------------------------------------------------------------
# EvaluationWorkerThread – signal emission
# ---------------------------------------------------------------------------


class TestEvaluationWorkerThread:
    """
    Tests for EvaluationWorkerThread signal emission.
    """

    def test_worker_emits_completed_signal(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Worker thread should emit evaluation_completed with the report on success.
        """
        mock_report = EvaluationReport(template_name="T", total_samples_checked=0)
        mock_controller = MagicMock()
        mock_controller.run_evaluation.return_value = mock_report

        worker = EvaluationWorkerThread(mock_controller)

        received: list[EvaluationReport] = []
        worker.evaluation_completed.connect(received.append)

        with qtbot.waitSignal(worker.evaluation_completed, timeout=3000):
            worker.run()

        assert len(received) == 1
        assert received[0].template_name == "T"

    def test_worker_emits_failed_signal_on_error(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qtbot):
        """
        Worker thread should emit evaluation_failed when run_evaluation raises.
        """
        mock_controller = MagicMock()
        mock_controller.run_evaluation.side_effect = RuntimeError("DB error")

        worker = EvaluationWorkerThread(mock_controller)

        errors: list[str] = []
        worker.evaluation_failed.connect(errors.append)

        with qtbot.waitSignal(worker.evaluation_failed, timeout=3000):
            worker.run()

        assert len(errors) == 1
        assert "DB error" in errors[0]


# ---------------------------------------------------------------------------
# WidgetDatasetTop – Tools menu integration
# ---------------------------------------------------------------------------


class TestToolsMenuEvaluationReport:
    """
    Tests that the Evaluation Report menu item is wired up correctly in WidgetDatasetTop.
    """

    def test_evaluation_report_action_exists(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", ensure_google_icon_font,
                                             qt_app):
        """
        WidgetDatasetTop should have an action_evaluation_report attribute.
        """
        from py_fade.gui.widget_dataset_top import WidgetDatasetTop  # pylint: disable=import-outside-toplevel

        widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
        try:
            assert widget.action_evaluation_report is not None
        finally:
            widget.close()

    def test_evaluation_report_action_label(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", ensure_google_icon_font,
                                            qt_app):
        """
        The evaluation report menu action should have the expected label.
        """
        from py_fade.gui.widget_dataset_top import WidgetDatasetTop  # pylint: disable=import-outside-toplevel

        widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
        try:
            assert "Evaluation" in widget.action_evaluation_report.text()
        finally:
            widget.close()
