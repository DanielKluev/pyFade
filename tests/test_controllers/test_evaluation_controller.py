"""
Tests for EvaluationController and related data classes.

Covers:
- EvaluationCriteria describe_criteria()
- EvaluationController.run_evaluation() with all three criteria
- Empty template handling
- YAML serialisation helper
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.evaluation_controller import (
    EvaluationController,
    EvaluationCriteria,
    EvaluationReport,
    IssueRecord,
    SampleIssueRecord,
)
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from tests.helpers.data_helpers import create_test_completion

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_template(dataset: "DatasetDatabase", facet: Facet, name: str = "Test Template") -> ExportTemplate:
    """
    Create a minimal SFT export template pointing at *facet*.
    """
    template = ExportTemplate.create(
        dataset,
        name=name,
        description="",
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


def _make_facet_sample_completion(dataset: "DatasetDatabase", facet: Facet, rating: int, title: str = "Sample A",
                                  completion_text: str = "Hello world") -> Sample:
    """
    Create a sample with one completion rated ``rating`` for ``facet``.
    """
    prompt_text = "FLAT_PREFIX_USER\nTest prompt\nFLAT_PREFIX_ASSISTANT\n"
    prompt_rev = PromptRevision.get_or_create(dataset, prompt_text, 2048, 512)
    sample = Sample.create_if_unique(dataset, title, prompt_rev, None)
    dataset.commit()

    completion = create_test_completion(dataset.session, prompt_rev, {"completion_text": completion_text})
    dataset.session.commit()

    PromptCompletionRating.set_rating(dataset, completion, facet, rating)
    return sample


# ---------------------------------------------------------------------------
# EvaluationCriteria tests
# ---------------------------------------------------------------------------


class TestEvaluationCriteria:
    """
    Tests for EvaluationCriteria.describe_criteria().
    """

    def test_default_criteria_lists_export_failures(self):
        """
        Default criteria should include the export-failure description only.
        """
        criteria = EvaluationCriteria()
        descriptions = criteria.describe_criteria()
        assert len(descriptions) == 1
        assert "export" in descriptions[0].lower()

    def test_high_rated_completions_described(self):
        """
        When min_high_rated_completions is set, describe_criteria includes it.
        """
        criteria = EvaluationCriteria(min_high_rated_completions=2, min_high_rated_threshold=9)
        descriptions = criteria.describe_criteria()
        combined = " ".join(descriptions)
        assert "2" in combined
        assert "9" in combined

    def test_completion_regex_described(self):
        """
        When completion_regex is set, describe_criteria mentions the pattern.
        """
        criteria = EvaluationCriteria(completion_regex=r"\bsorry\b", completion_regex_top_n=5)
        descriptions = criteria.describe_criteria()
        combined = " ".join(descriptions)
        assert "sorry" in combined
        assert "5" in combined

    def test_all_criteria_active(self):
        """
        All three criteria types should be present when fully enabled.
        """
        criteria = EvaluationCriteria(
            check_export_failures=True,
            min_high_rated_completions=3,
            min_high_rated_threshold=10,
            completion_regex=r"bad",
            completion_regex_top_n=2,
        )
        descriptions = criteria.describe_criteria()
        assert len(descriptions) == 3

    def test_no_active_criteria(self):
        """
        With everything disabled, describe_criteria should return an empty list.
        """
        criteria = EvaluationCriteria(check_export_failures=False)
        assert criteria.describe_criteria() == []


# ---------------------------------------------------------------------------
# EvaluationReport tests
# ---------------------------------------------------------------------------


class TestEvaluationReport:
    """
    Tests for EvaluationReport helper properties.
    """

    def test_total_samples_with_issues_count(self):
        """
        total_samples_with_issues should equal the length of samples_with_issues.
        """
        report = EvaluationReport(
            template_name="T",
            samples_with_issues=[
                SampleIssueRecord(1, "A", None, 1, "facet", [IssueRecord("t", "d")]),
                SampleIssueRecord(2, "B", None, 1, "facet", [IssueRecord("t", "d")]),
            ],
        )
        assert report.total_samples_with_issues == 2

    def test_empty_report(self):
        """
        A freshly created report has zero issues.
        """
        report = EvaluationReport(template_name="T")
        assert report.total_samples_with_issues == 0
        assert report.total_samples_checked == 0


# ---------------------------------------------------------------------------
# EvaluationController - export failures criterion
# ---------------------------------------------------------------------------


class TestEvaluationControllerExportFailures:
    """
    Tests for the standard-export-failure criterion in EvaluationController.
    """

    def test_no_logprobs_for_target_model_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample with a completion that has no logprobs for the resolved target model
        should be reported as an export failure.
        """
        facet = Facet.create(temp_dataset, "Facet A", "desc", min_rating=6)
        temp_dataset.commit()

        # Create a sample with a high-rated completion but NO logprobs.
        _make_facet_sample_completion(temp_dataset, facet, rating=8, title="No Logprobs Sample")

        template = _make_template(temp_dataset, facet)
        # Explicitly pass a model ID that will be used for logprob checking.
        # Since the completion has no logprobs, validation will fail.
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=True),
            target_model_id="mock-echo-model",
        )

        report = controller.run_evaluation()

        assert report.total_samples_checked == 1
        assert report.total_samples_with_issues == 1
        issue_types = [i.issue_type for r in report.samples_with_issues for i in r.issues]
        assert "export_failure" in issue_types

    def test_completion_at_exact_min_rating_passes(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample with a completion rated exactly at min_rating should pass the threshold check.
        (Boundary: rating == min_rating is acceptable.)
        """
        facet = Facet.create(temp_dataset, "Facet B", "desc", min_rating=7)
        temp_dataset.commit()

        # Create a sample with a completion rated exactly at min_rating and add logprobs.
        from tests.helpers.data_helpers import create_test_logprobs  # pylint: disable=import-outside-toplevel

        prompt_text = "FLAT_PREFIX_USER\nBoundary test\nFLAT_PREFIX_ASSISTANT\n"
        prompt_rev = PromptRevision.get_or_create(temp_dataset, prompt_text, 2048, 512)
        Sample.create_if_unique(temp_dataset, "Boundary Sample", prompt_rev, None)
        temp_dataset.commit()

        completion = create_test_completion(temp_dataset.session, prompt_rev, {"completion_text": "Adequate answer"})
        temp_dataset.session.commit()
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 7)  # Exactly at min_rating.
        create_test_logprobs(temp_dataset, completion.id, "mock-echo-model", min_logprob=-0.5, avg_logprob=-0.2)
        temp_dataset.session.commit()

        template = _make_template(temp_dataset, facet)
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=True),
            target_model_id="mock-echo-model",
        )

        report = controller.run_evaluation()

        assert report.total_samples_checked == 1
        assert report.total_samples_with_issues == 0

    def test_passing_sample_not_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample with a well-rated completion and passing logprobs should not be reported.
        """
        from tests.helpers.data_helpers import create_test_logprobs  # pylint: disable=import-outside-toplevel

        facet = Facet.create(temp_dataset, "Facet C", "desc", min_rating=6)
        temp_dataset.commit()

        prompt_text = "FLAT_PREFIX_USER\nGood sample\nFLAT_PREFIX_ASSISTANT\n"
        prompt_rev = PromptRevision.get_or_create(temp_dataset, prompt_text, 2048, 512)
        Sample.create_if_unique(temp_dataset, "Good Sample", prompt_rev, None)
        temp_dataset.commit()

        completion = create_test_completion(temp_dataset.session, prompt_rev, {"completion_text": "Good answer"})
        temp_dataset.session.commit()
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 8)
        create_test_logprobs(temp_dataset, completion.id, "mock-echo-model", min_logprob=-0.5, avg_logprob=-0.2)
        temp_dataset.session.commit()

        template = _make_template(temp_dataset, facet)
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=True),
            target_model_id="mock-echo-model",
        )

        report = controller.run_evaluation()

        assert report.total_samples_checked == 1
        assert report.total_samples_with_issues == 0

    def test_below_min_rating_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample whose only rated completion is below the facet's min_rating should be reported.
        The controller should NOT pass any target_model_id, so the logprob check is skipped
        and the failure is clearly due to the rating threshold.
        """
        facet = Facet.create(temp_dataset, "Facet D", "desc", min_rating=7)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=5, title="Low Rated Sample")

        template = _make_template(temp_dataset, facet)
        # Explicitly set an unknown target_model_id so no logprob fallback occurs,
        # ensuring the failure is due to the rating threshold only.
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=True),
            target_model_id="no-such-model-id",
        )

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 1
        descriptions = " ".join(i.description for r in report.samples_with_issues for i in r.issues)
        assert "7" in descriptions

    def test_export_failure_disabled(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        With check_export_failures=False, low-rated samples should not be reported for export failures.
        """
        facet = Facet.create(temp_dataset, "Facet E", "desc", min_rating=7)
        temp_dataset.commit()

        # Sample with a low-rated completion that would normally fail the export check.
        _make_facet_sample_completion(temp_dataset, facet, rating=3, title="Low Rated")

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(check_export_failures=False)
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=criteria,
            target_model_id="no-such-model-id",
        )

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 0


# ---------------------------------------------------------------------------
# EvaluationController - high-rated completions criterion
# ---------------------------------------------------------------------------


class TestEvaluationControllerHighRated:
    """
    Tests for the minimum high-rated completions criterion.
    """

    def test_insufficient_high_rated_completions_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample with only one completion rated >= 9 should be flagged when min=2.
        """
        facet = Facet.create(temp_dataset, "Facet F", "desc", min_rating=1)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=9, title="One Good Completion", completion_text="Comp A")

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=False,
            min_high_rated_completions=2,
            min_high_rated_threshold=9,
        )
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 1
        issue_types = [i.issue_type for r in report.samples_with_issues for i in r.issues]
        assert "high_rated_count" in issue_types

    def test_sufficient_high_rated_completions_not_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample with two completions rated >= 9 should pass when min=2.
        """
        facet = Facet.create(temp_dataset, "Facet G", "desc", min_rating=1)
        temp_dataset.commit()

        prompt_text = "FLAT_PREFIX_USER\nTest\nFLAT_PREFIX_ASSISTANT\n"
        prompt_rev = PromptRevision.get_or_create(temp_dataset, prompt_text, 2048, 512)
        sample = Sample.create_if_unique(temp_dataset, "Two Good Completions", prompt_rev, None)
        temp_dataset.commit()
        assert sample is not None  # Ensure sample was created.

        # Add two completions rated >= 9.
        for i in range(2):
            comp = create_test_completion(temp_dataset.session, prompt_rev, {"completion_text": f"Great answer {i}"})
            temp_dataset.session.commit()
            PromptCompletionRating.set_rating(temp_dataset, comp, facet, 9)

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=False,
            min_high_rated_completions=2,
            min_high_rated_threshold=9,
        )
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 0

    def test_rating_exactly_at_threshold_counts(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A completion rated exactly at the threshold (e.g. 10 when threshold=10) counts.
        """
        facet = Facet.create(temp_dataset, "Facet H", "desc", min_rating=1)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=10, title="Perfect Completion", completion_text="Perfect")

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=False,
            min_high_rated_completions=1,
            min_high_rated_threshold=10,
        )
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 0


# ---------------------------------------------------------------------------
# EvaluationController - completion regex criterion
# ---------------------------------------------------------------------------


class TestEvaluationControllerCompletionRegex:
    """
    Tests for the completion regex criterion.
    """

    def test_matching_completion_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A completion matching the configured regex should be reported.
        """
        facet = Facet.create(temp_dataset, "Facet I", "desc", min_rating=1)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=8, title="Refusal Sample", completion_text="I'm sorry, I cannot help.")

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=False,
            completion_regex=r"I'm sorry",
            completion_regex_top_n=3,
        )
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 1
        issue_types = [i.issue_type for r in report.samples_with_issues for i in r.issues]
        assert "completion_regex" in issue_types

    def test_non_matching_completion_not_reported(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A completion that does not match the regex should not be reported.
        """
        facet = Facet.create(temp_dataset, "Facet J", "desc", min_rating=1)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=9, title="Clean Sample", completion_text="Here is the answer.")

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(check_export_failures=False, completion_regex=r"I'm sorry", completion_regex_top_n=3)
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 0

    def test_invalid_regex_raises_value_error(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        An invalid regex pattern should raise ValueError before the evaluation starts.
        """
        facet = Facet.create(temp_dataset, "Facet K", "desc")
        temp_dataset.commit()

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(check_export_failures=False, completion_regex=r"[invalid")
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        with pytest.raises(ValueError, match="Invalid completion_regex"):
            controller.run_evaluation()

    def test_top_n_boundary(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        With top_n=1, only the single highest-rated completion is checked.

        If only a low-rated completion matches the regex, no issue should be reported
        when top_n=1 restricts checking to the highest-rated one.
        """
        facet = Facet.create(temp_dataset, "Facet L", "desc", min_rating=1)
        temp_dataset.commit()

        prompt_text = "FLAT_PREFIX_USER\nTest top N\nFLAT_PREFIX_ASSISTANT\n"
        prompt_rev = PromptRevision.get_or_create(temp_dataset, prompt_text, 2048, 512)
        Sample.create_if_unique(temp_dataset, "Top-N Sample", prompt_rev, None)
        temp_dataset.commit()

        # High-rated completion - no regex match.
        comp_high = create_test_completion(temp_dataset.session, prompt_rev, {"completion_text": "Good answer"})
        temp_dataset.session.commit()
        PromptCompletionRating.set_rating(temp_dataset, comp_high, facet, 9)

        # Low-rated completion - matches regex.
        comp_low = create_test_completion(temp_dataset.session, prompt_rev, {"completion_text": "I'm sorry I cannot."})
        temp_dataset.session.commit()
        PromptCompletionRating.set_rating(temp_dataset, comp_low, facet, 3)

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=False,
            completion_regex=r"I'm sorry",
            completion_regex_top_n=1,  # Only check the highest-rated completion.
        )
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)

        report = controller.run_evaluation()

        # The highest-rated completion doesn't match, so no issue.
        assert report.total_samples_with_issues == 0


# ---------------------------------------------------------------------------
# EvaluationController - combined criteria
# ---------------------------------------------------------------------------


class TestEvaluationControllerCombined:
    """
    Tests for combining multiple criteria in a single evaluation run.
    """

    def test_multiple_issues_per_sample(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A sample can have issues from multiple criteria simultaneously.
        """
        facet = Facet.create(temp_dataset, "Facet M", "desc", min_rating=8)
        temp_dataset.commit()

        # Completion rated 5 (fails export threshold) and matches regex.
        _make_facet_sample_completion(
            temp_dataset,
            facet,
            rating=5,
            title="Multi-Issue Sample",
            completion_text="I'm sorry, I cannot help.",
        )

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(
            check_export_failures=True,
            min_high_rated_completions=1,
            min_high_rated_threshold=9,
            completion_regex=r"I'm sorry",
            completion_regex_top_n=3,
        )
        # Use a non-existent model ID so only the rating check drives export_failure
        # (no logprob check interference).
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=criteria,
            target_model_id="no-such-model-id",
        )

        report = controller.run_evaluation()

        assert report.total_samples_with_issues == 1
        issue_types = {i.issue_type for r in report.samples_with_issues for i in r.issues}
        assert "export_failure" in issue_types
        assert "high_rated_count" in issue_types
        assert "completion_regex" in issue_types

    def test_empty_template_no_facets(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        A template with no facets should produce a report with zero samples checked.
        """
        template = ExportTemplate.create(
            temp_dataset,
            name="Empty Template",
            description="",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Gemma3"],
            facets=[],
        )
        temp_dataset.commit()

        controller = EvaluationController(app_with_dataset, temp_dataset, template)
        report = controller.run_evaluation()

        assert report.total_samples_checked == 0
        assert report.total_samples_with_issues == 0

    def test_progress_callback_invoked(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        The progress callback should be called at least once per sample.
        """
        facet = Facet.create(temp_dataset, "Facet N", "desc", min_rating=1)
        temp_dataset.commit()

        _make_facet_sample_completion(temp_dataset, facet, rating=7, title="CB Sample")

        template = _make_template(temp_dataset, facet)

        calls: list[tuple] = []

        def _cb(*args):
            calls.append(args)

        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=False),
            progress_callback=_cb,
        )
        controller.run_evaluation()

        assert len(calls) >= 1

    def test_report_template_name(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        The report's template_name should match the template used.
        """
        facet = Facet.create(temp_dataset, "Facet O", "desc")
        temp_dataset.commit()

        template = _make_template(temp_dataset, facet, name="My Special Template")
        controller = EvaluationController(
            app_with_dataset,
            temp_dataset,
            template,
            criteria=EvaluationCriteria(check_export_failures=False),
        )
        report = controller.run_evaluation()

        assert report.template_name == "My Special Template"

    def test_criteria_applied_list_in_report(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        The criteria_applied list in the report should match the active criteria.
        """
        facet = Facet.create(temp_dataset, "Facet P", "desc", min_rating=1)
        temp_dataset.commit()

        template = _make_template(temp_dataset, facet)
        criteria = EvaluationCriteria(check_export_failures=True, min_high_rated_completions=2, min_high_rated_threshold=9)
        controller = EvaluationController(app_with_dataset, temp_dataset, template, criteria=criteria)
        report = controller.run_evaluation()

        assert len(report.criteria_applied) == 2

    def test_missing_dataset_session_raises(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        run_evaluation should raise RuntimeError when the database session is not initialised.
        """
        facet = Facet.create(temp_dataset, "Facet Q", "desc")
        temp_dataset.commit()
        template = _make_template(temp_dataset, facet)

        temp_dataset.dispose()
        temp_dataset.session = None

        controller = EvaluationController(app_with_dataset, temp_dataset, template)
        with pytest.raises(RuntimeError, match="session is not initialized"):
            controller.run_evaluation()
