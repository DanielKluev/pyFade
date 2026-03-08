"""
Middle layer to control evaluation report operation.

Runs an export template in dry-run mode and reports per-sample issues
based on configurable criteria, without writing any output file.
"""

import logging
import re
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.providers.flat_prefix_template import parse_flat_prefix_string

if TYPE_CHECKING:
    from typing import Callable
    from py_fade.app import PyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.export_template import ExportTemplate
    from py_fade.dataset.completion import PromptCompletion


@dataclass
class IssueRecord:
    """
    A single issue found for a sample during evaluation.

    Attributes:
        issue_type: Machine-readable issue category (e.g. "export_failure").
        description: Human-readable description of the specific problem.
    """

    issue_type: str
    description: str


@dataclass
class SampleIssueRecord:
    """
    Aggregated issues for a single sample within one facet.

    Attributes:
        sample_id: Database ID of the sample.
        sample_title: Display title of the sample.
        group_path: Optional path of the group this sample belongs to.
        facet_id: Database ID of the facet being evaluated.
        facet_name: Display name of the facet.
        issues: List of individual issues found.
    """

    sample_id: int
    sample_title: str
    group_path: str | None
    facet_id: int
    facet_name: str
    issues: list[IssueRecord] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """
    Full evaluation report across all facets processed from a template.

    Attributes:
        template_name: Name of the export template that was evaluated.
        total_samples_checked: Total number of samples processed across all facets.
        samples_with_issues: Samples that have at least one issue.
        criteria_applied: Human-readable descriptions of all criteria that were active.
    """

    template_name: str
    total_samples_checked: int = 0
    samples_with_issues: list[SampleIssueRecord] = field(default_factory=list)
    criteria_applied: list[str] = field(default_factory=list)

    @property
    def total_samples_with_issues(self) -> int:
        """
        Return the number of samples that have at least one issue.
        """
        return len(self.samples_with_issues)


@dataclass
class EvaluationCriteria:
    """
    Configurable criteria for the evaluation report.

    Each attribute enables or parametrises one category of issue detection.

    Attributes:
        check_export_failures: When True, report samples that would fail the standard
            export validation (unfinished, no rated completions, below thresholds, etc.).
        min_high_rated_completions: When set, report samples that have fewer than this
            many completions with a rating >= ``min_high_rated_threshold`` for the facet.
        min_high_rated_threshold: Rating threshold used by the ``min_high_rated_completions``
            check.  Typical values are 9 or 10.
        completion_regex: When set, report samples where any of the top
            ``completion_regex_top_n`` completions (by rating) match this regex pattern.
        completion_regex_top_n: Number of top-rated completions to check against
            ``completion_regex``.
    """

    check_export_failures: bool = True
    min_high_rated_completions: int | None = None
    min_high_rated_threshold: int = 9
    completion_regex: str | None = None
    completion_regex_top_n: int = 3

    def describe_criteria(self) -> list[str]:
        """
        Return a list of human-readable descriptions for all active criteria.
        """
        descriptions = []
        if self.check_export_failures:
            descriptions.append("Standard export validation (unfinished, missing ratings, below thresholds)")
        if self.min_high_rated_completions is not None:
            descriptions.append(f"High-rated completions: at least {self.min_high_rated_completions} "
                                f"completions with rating >= {self.min_high_rated_threshold} required")
        if self.completion_regex:
            descriptions.append(f"Completion regex match in top {self.completion_regex_top_n}: pattern='{self.completion_regex}'")
        return descriptions


class EvaluationController:
    """
    EvaluationController runs an export template in dry-run mode and collects per-sample issues.

    The controller iterates over all facets and samples defined by the export template,
    applying all active criteria from the provided ``EvaluationCriteria`` to each sample.
    No file output is produced; results are stored in ``evaluation_report``.
    """

    def __init__(self, app: "PyFadeApp", dataset: "DatasetDatabase", export_template: "ExportTemplate",
                 criteria: "EvaluationCriteria | None" = None, target_model_id: str | None = None,
                 progress_callback: "Callable[[int, int, str, int, int], None] | None" = None) -> None:
        """
        Initialise the controller.

        Args:
            app: Main application instance (used to resolve providers).
            dataset: Dataset database to evaluate.
            export_template: Export template whose facet configuration drives the evaluation.
            criteria: Issue-detection criteria.  Defaults to ``EvaluationCriteria()``
                (export failures only).
            target_model_id: Model ID used for logprob threshold checks.  Falls back to the
                first mapped model when not provided.
            progress_callback: Optional callback invoked with
                ``(current_facet_idx, total_facets, facet_name, current_sample, total_samples)``
                as evaluation proceeds.
        """
        self.log = logging.getLogger("EvaluationController")
        self.app = app
        self.dataset = dataset
        self.export_template = export_template
        self.criteria = criteria if criteria is not None else EvaluationCriteria()
        self.target_model_id = target_model_id
        self.progress_callback = progress_callback
        self.evaluation_report: EvaluationReport | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_evaluation(self) -> "EvaluationReport":
        """
        Run the evaluation and return the completed report.

        Iterates over all facets in the export template, applies all active criteria to
        each sample, and records issues in ``evaluation_report``.

        Returns:
            The completed ``EvaluationReport``. If the export template has no facets
            configured, an empty report is returned and a warning is logged.

        Raises:
            RuntimeError: If the dataset session is not initialised.
        """
        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")

        self.evaluation_report = EvaluationReport(
            template_name=self.export_template.name,
            criteria_applied=self.criteria.describe_criteria(),
        )

        # Validate regex up-front so we can produce a clear error early.
        compiled_regex = self._compile_regex()

        total_facets = len(self.export_template.facets_json)
        if total_facets == 0:
            self.log.warning("Export template '%s' has no facets configured", self.export_template.name)
            return self.evaluation_report

        current_facet_idx = 0

        for facet_config in self.export_template.facets_json:
            facet_id = facet_config["facet_id"]
            current_facet_idx += 1

            facet = Facet.get_by_id(self.dataset, facet_id)
            if not facet:
                self.log.warning("Facet %d not found, skipping", facet_id)
                continue

            self._evaluate_facet(facet, facet_config, current_facet_idx, total_facets, compiled_regex)

        self.log.info(
            "Evaluation complete: %d samples checked, %d with issues",
            self.evaluation_report.total_samples_checked,
            self.evaluation_report.total_samples_with_issues,
        )
        return self.evaluation_report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compile_regex(self) -> "re.Pattern[str] | None":
        """
        Compile the regex pattern from criteria.

        Returns:
            A compiled pattern, or ``None`` when ``completion_regex`` is not set.

        Raises:
            ValueError: If the pattern is invalid.
        """
        if not self.criteria.completion_regex:
            return None
        try:
            return re.compile(self.criteria.completion_regex)
        except re.error as exc:
            raise ValueError(f"Invalid completion_regex pattern: {exc}") from exc

    def _evaluate_facet(self, facet: Facet, facet_config: dict, current_facet_idx: int, total_facets: int,
                        compiled_regex: "re.Pattern[str] | None") -> None:
        """
        Evaluate all samples in a single facet and record issues.

        Args:
            facet: Facet object to evaluate.
            facet_config: Configuration dict from the export template for this facet.
            current_facet_idx: 1-based index of this facet (for progress reporting).
            total_facets: Total number of facets (for progress reporting).
            compiled_regex: Pre-compiled regex pattern, or ``None`` if disabled.
        """
        # Resolve thresholds – same logic as ExportController.
        min_rating = facet_config.get("min_rating")
        if min_rating is None:
            min_rating = facet.min_rating
        min_logprob = facet_config.get("min_logprob")
        if min_logprob is None:
            min_logprob = facet.min_logprob_threshold
        avg_logprob = facet_config.get("avg_logprob")
        if avg_logprob is None:
            avg_logprob = facet.avg_logprob_threshold

        # Resolve target model ID for logprob checks.
        target_model_id = self._resolve_target_model_id()

        # Get samples for this facet.
        samples = facet.get_samples(self.dataset)

        # Apply ordering (mirrors ExportController behaviour).
        order = facet_config.get("order", "random")
        if order == "newest":
            samples = sorted(samples, key=lambda s: s.date_created, reverse=True)
        elif order == "oldest":
            samples = sorted(samples, key=lambda s: s.date_created)
        else:
            samples = list(samples)
            random.shuffle(samples)

        # Apply limit.
        limit_type = facet_config.get("limit_type", "percentage")
        limit_value = facet_config.get("limit_value", 100)
        if limit_type == "percentage":
            max_samples = max(1, int(len(samples) * limit_value / 100.0))
        else:
            max_samples = int(limit_value)

        evaluated_count = 0

        if self.progress_callback:
            self.progress_callback(current_facet_idx, total_facets, facet.name, 0, max_samples)

        for sample in samples:
            if evaluated_count >= max_samples:
                break

            evaluated_count += 1
            self.evaluation_report.total_samples_checked += 1

            if self.progress_callback:
                self.progress_callback(current_facet_idx, total_facets, facet.name, min(evaluated_count, max_samples), max_samples)

            issues = self._evaluate_sample(sample, facet, min_rating, min_logprob, avg_logprob, target_model_id, compiled_regex)

            if issues:
                self.evaluation_report.samples_with_issues.append(
                    SampleIssueRecord(
                        sample_id=sample.id,
                        sample_title=sample.title,
                        group_path=sample.group_path,
                        facet_id=facet.id,
                        facet_name=facet.name,
                        issues=issues,
                    ))

    def _evaluate_sample(self, sample: Sample, facet: Facet, min_rating: int, min_logprob: float, avg_logprob: float,
                         target_model_id: "str | None", compiled_regex: "re.Pattern[str] | None") -> list[IssueRecord]:
        """
        Apply all active criteria to a single sample and return any issues found.

        Args:
            sample: The sample to check.
            facet: Facet used for rating lookups.
            min_rating: Minimum rating threshold (from template / facet defaults).
            min_logprob: Minimum token logprob threshold.
            avg_logprob: Average token logprob threshold.
            target_model_id: Model ID for logprob checks.
            compiled_regex: Pre-compiled regex pattern to match against completions.

        Returns:
            List of ``IssueRecord`` objects.  Empty list means the sample is clean.
        """
        issues: list[IssueRecord] = []

        if self.criteria.check_export_failures:
            issues.extend(self._check_export_failures(sample, facet, min_rating, min_logprob, avg_logprob, target_model_id))

        if self.criteria.min_high_rated_completions is not None:
            issues.extend(self._check_high_rated_completions(sample, facet))

        if compiled_regex is not None:
            issues.extend(self._check_completion_regex(sample, facet, compiled_regex))

        return issues

    def _check_export_failures(self, sample: Sample, facet: Facet, min_rating: int, min_logprob: float, avg_logprob: float,
                               target_model_id: "str | None") -> list[IssueRecord]:
        """
        Check if the sample would fail the standard SFT export validation.

        Mirrors the validation logic inside ExportController._sample_to_conversations_with_validation.

        Args:
            sample: Sample to validate.
            facet: Facet used for rating lookups.
            min_rating: Minimum completion rating threshold.
            min_logprob: Minimum token logprob threshold.
            avg_logprob: Average token logprob threshold.
            target_model_id: Model ID for logprob checks.

        Returns:
            List of ``IssueRecord`` objects describing validation failures.
        """
        issues: list[IssueRecord] = []

        # Unfinished sample (no prompt revision or completions).
        if sample.is_unfinished(self.dataset):
            issues.append(IssueRecord(issue_type="export_failure", description="Sample is unfinished"))
            return issues

        if not sample.prompt_revision or not sample.prompt_revision.completions:
            issues.append(IssueRecord(issue_type="export_failure", description="No prompt revision or completions"))
            return issues

        # Validate prompt text is parseable.
        try:
            parse_flat_prefix_string(sample.prompt_revision.prompt_text)
        except ValueError as exc:
            issues.append(IssueRecord(issue_type="export_failure", description=f"Failed to parse prompt text: {exc}"))
            return issues

        # Collect rated completions for this facet.
        rated_completions = []
        for completion in sample.prompt_revision.completions:
            rating_obj = completion.rating_for_facet(facet)
            if rating_obj:
                rated_completions.append((completion, rating_obj.rating))

        if not rated_completions:
            issues.append(IssueRecord(issue_type="export_failure", description="No rated completions found for this facet"))
            return issues

        # Check rating threshold.
        high_rated = [comp for comp, rating in rated_completions if rating >= min_rating]
        if not high_rated:
            max_rating = max(rating for _, rating in rated_completions)
            issues.append(
                IssueRecord(issue_type="export_failure",
                            description=f"No completion with rating >= {min_rating} (max rating: {max_rating})"))
            return issues

        # Check logprob thresholds.
        if target_model_id:
            valid_completions = []
            for completion in high_rated:
                logprobs = completion.get_logprobs_for_model_id(target_model_id)
                if logprobs and logprobs.min_logprob >= min_logprob and logprobs.avg_logprob >= avg_logprob:
                    valid_completions.append(completion)

            if not valid_completions:
                logprob_details = []
                for completion in high_rated:
                    logprobs = completion.get_logprobs_for_model_id(target_model_id)
                    if not logprobs:
                        logprob_details.append(f"completion {completion.id}: no logprobs for target model")
                    else:
                        if logprobs.min_logprob < min_logprob:
                            logprob_details.append(f"completion {completion.id}: min_logprob {logprobs.min_logprob:.3f} < {min_logprob}")
                        if logprobs.avg_logprob < avg_logprob:
                            logprob_details.append(f"completion {completion.id}: avg_logprob {logprobs.avg_logprob:.3f} < {avg_logprob}")
                detail_str = "; ".join(logprob_details) if logprob_details else "no details available"
                issues.append(
                    IssueRecord(issue_type="export_failure",
                                description=f"No high-rated completion meets logprob thresholds ({detail_str})"))

        return issues

    def _check_high_rated_completions(self, sample: Sample, facet: Facet) -> list[IssueRecord]:
        """
        Check whether the sample has enough high-rated completions.

        Reports an issue when the count of completions with rating >=
        ``criteria.min_high_rated_threshold`` is less than
        ``criteria.min_high_rated_completions``.

        Args:
            sample: Sample to check.
            facet: Facet used for rating lookups.

        Returns:
            List with a single ``IssueRecord`` if the check fails, otherwise empty.
        """
        min_count = self.criteria.min_high_rated_completions
        threshold = self.criteria.min_high_rated_threshold

        if not sample.prompt_revision or not sample.prompt_revision.completions:
            return [
                IssueRecord(
                    issue_type="high_rated_count",
                    description=f"No completions available (need {min_count} with rating >= {threshold})",
                )
            ]

        count = 0
        for completion in sample.prompt_revision.completions:
            rating_obj = completion.rating_for_facet(facet)
            if rating_obj is not None and rating_obj.rating >= threshold:
                count += 1

        if count < min_count:
            return [
                IssueRecord(
                    issue_type="high_rated_count",
                    description=f"Only {count}/{min_count} completions with rating >= {threshold}",
                )
            ]
        return []

    def _check_completion_regex(self, sample: Sample, facet: Facet, compiled_regex: "re.Pattern[str]") -> list[IssueRecord]:
        """
        Check whether any of the top-N rated completions match the configured regex.

        Reports an issue for each matching completion found among the top
        ``criteria.completion_regex_top_n`` completions (sorted by rating descending).

        Args:
            sample: Sample to check.
            facet: Facet used for rating sorting.
            compiled_regex: Pre-compiled regex pattern.

        Returns:
            List of ``IssueRecord`` objects for each matching completion.
        """
        if not sample.prompt_revision or not sample.prompt_revision.completions:
            return []

        # Build (completion, rating) list and sort by rating descending.
        rated: list[tuple["PromptCompletion", int]] = []
        for completion in sample.prompt_revision.completions:
            rating_obj = completion.rating_for_facet(facet)
            rating = rating_obj.rating if rating_obj else 0
            rated.append((completion, rating))

        rated.sort(key=lambda x: x[1], reverse=True)
        top_n = rated[:self.criteria.completion_regex_top_n]

        issues: list[IssueRecord] = []
        for completion, rating in top_n:
            if compiled_regex.search(completion.completion_text):
                issues.append(
                    IssueRecord(
                        issue_type="completion_regex",
                        description=(f"Completion (rating={rating}) matches regex "
                                     f"'{self.criteria.completion_regex}'"),
                    ))
        return issues

    def _resolve_target_model_id(self) -> "str | None":
        """
        Resolve the effective target model ID for logprob checks.

        Uses the explicitly provided ``target_model_id`` if available, otherwise
        falls back to the first mapped model in the providers manager.

        Returns:
            Model ID string, or ``None`` if no model is available.
        """
        if self.target_model_id:
            return self.target_model_id
        if hasattr(self.app, "providers_manager") and self.app.providers_manager.model_provider_map:
            first_mapped = next(iter(self.app.providers_manager.model_provider_map.values()))
            self.log.debug("No target model specified, using fallback model: %s", first_mapped.model_id)
            return first_mapped.model_id
        return None
