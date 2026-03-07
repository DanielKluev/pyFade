"""
Tests for the Multiple Completions per SFT Sample feature.

Covers:
- ExportTemplate model: new completions_per_sample and facet_balancing_factor fields
  (creation, update, validation, duplication, normalization)
- ExportController: multi-completion SFT export with K > 1, K = M, K > M, K = 1 (regression)
- ExportController: facet_balancing_factor > 0 raises NotImplementedError
- FacetExportSummary: partial_completion_samples tracking
"""
# pylint: disable=protected-access

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.export_controller import ExportController, FacetExportSummary
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.providers.flat_prefix_template import FLAT_PREFIX_USER
from tests.helpers.data_helpers import create_completion_with_rating_and_logprobs
from tests.helpers.export_wizard_helpers import (
    create_and_run_export_test,
    setup_facet_sample_and_completion,
)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.dataset.prompt import PromptRevision
    from py_fade.app import pyFadeApp

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sft_template(dataset: "DatasetDatabase", facet: Facet, completions_per_sample: int = 1, facet_balancing_factor: float = 0.0,
                       name: str = "Test Template") -> ExportTemplate:
    """
    Create an SFT export template with completions_per_sample and facet_balancing_factor set.
    """
    template = ExportTemplate.create(
        dataset,
        name=name,
        description="Multi-completion export template",
        training_type="SFT",
        output_format="JSONL (ShareGPT)",
        model_families=["Llama3"],
        facets=[{
            "facet_id": facet.id,
            "limit_type": "count",
            "limit_value": 1000,
            "order": "random",
        }],
        completions_per_sample=completions_per_sample,
        facet_balancing_factor=facet_balancing_factor,
    )
    dataset.commit()
    return template


def _add_completion(dataset: "DatasetDatabase", prompt_rev: "PromptRevision", model_id: str, facet: Facet, rating: int, text: str,
                    min_logprob: float = -0.3, avg_logprob: float = -0.2):
    """
    Shorthand to add a rated completion with logprobs to a prompt revision.
    """
    return create_completion_with_rating_and_logprobs(dataset, prompt_rev, text, model_id, facet, rating=rating, min_logprob=min_logprob,
                                                      avg_logprob=avg_logprob)


def _run_export_and_load(app: "pyFadeApp", dataset: "DatasetDatabase", template: ExportTemplate,
                         model_id: str) -> tuple[ExportController, list[dict], pathlib.Path]:
    """
    Run a full export and return (controller, loaded_jsonl_entries, output_path).
    """
    controller, temp_path = create_and_run_export_test(app, dataset, template, target_model_id=model_id)
    try:
        controller.run_export()
        entries = []
        with open(temp_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return controller, entries, temp_path
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


# ===========================================================================
# ExportTemplate model tests
# ===========================================================================


class TestExportTemplateNewFields:
    """
    Tests for the new completions_per_sample and facet_balancing_factor fields
    on the ExportTemplate model.
    """

    def test_create_defaults(self, temp_dataset: "DatasetDatabase"):
        """
        Test that ExportTemplate.create() defaults completions_per_sample to 1 and
        facet_balancing_factor to 0.0.
        """
        facet = Facet.create(temp_dataset, "F", "desc")
        temp_dataset.commit()

        template = ExportTemplate.create(
            temp_dataset,
            name="T",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 10,
                "order": "random"
            }],
        )
        temp_dataset.commit()

        assert template.completions_per_sample == 1
        assert template.facet_balancing_factor == 0.0

    def test_create_custom_values(self, temp_dataset: "DatasetDatabase"):
        """
        Test that ExportTemplate.create() stores custom completions_per_sample and
        facet_balancing_factor.
        """
        facet = Facet.create(temp_dataset, "F2", "desc")
        temp_dataset.commit()

        template = ExportTemplate.create(
            temp_dataset,
            name="T2",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 10,
                "order": "random"
            }],
            completions_per_sample=3,
            facet_balancing_factor=0.5,
        )
        temp_dataset.commit()

        assert template.completions_per_sample == 3
        assert template.facet_balancing_factor == 0.5

    def test_create_invalid_completions_per_sample(self, temp_dataset: "DatasetDatabase"):
        """
        Test that completions_per_sample < 1 raises ValueError on create.
        """
        facet = Facet.create(temp_dataset, "F3", "desc")
        temp_dataset.commit()

        with pytest.raises(ValueError, match="completions_per_sample must be at least 1"):
            ExportTemplate.create(
                temp_dataset,
                name="T3",
                description="d",
                training_type="SFT",
                output_format="JSONL (ShareGPT)",
                model_families=["Llama3"],
                facets=[{
                    "facet_id": facet.id,
                    "limit_type": "count",
                    "limit_value": 10,
                    "order": "random"
                }],
                completions_per_sample=0,
            )

    def test_create_invalid_facet_balancing_factor(self, temp_dataset: "DatasetDatabase"):
        """
        Test that facet_balancing_factor < 0 raises ValueError on create.
        """
        facet = Facet.create(temp_dataset, "F4", "desc")
        temp_dataset.commit()

        with pytest.raises(ValueError, match="facet_balancing_factor must be >= 0"):
            ExportTemplate.create(
                temp_dataset,
                name="T4",
                description="d",
                training_type="SFT",
                output_format="JSONL (ShareGPT)",
                model_families=["Llama3"],
                facets=[{
                    "facet_id": facet.id,
                    "limit_type": "count",
                    "limit_value": 10,
                    "order": "random"
                }],
                facet_balancing_factor=-1.0,
            )

    def test_update_completions_per_sample(self, temp_dataset: "DatasetDatabase"):
        """
        Test that ExportTemplate.update() changes completions_per_sample correctly.
        """
        facet = Facet.create(temp_dataset, "F5", "desc")
        temp_dataset.commit()

        template = ExportTemplate.create(
            temp_dataset,
            name="T5",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 10,
                "order": "random"
            }],
        )
        temp_dataset.commit()
        assert template.completions_per_sample == 1

        template.update(temp_dataset, completions_per_sample=5)
        temp_dataset.commit()
        assert template.completions_per_sample == 5

    def test_update_facet_balancing_factor(self, temp_dataset: "DatasetDatabase"):
        """
        Test that ExportTemplate.update() changes facet_balancing_factor correctly.
        """
        facet = Facet.create(temp_dataset, "F6", "desc")
        temp_dataset.commit()

        template = ExportTemplate.create(
            temp_dataset,
            name="T6",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 10,
                "order": "random"
            }],
        )
        temp_dataset.commit()
        assert template.facet_balancing_factor == 0.0

        template.update(temp_dataset, facet_balancing_factor=1.5)
        temp_dataset.commit()
        assert template.facet_balancing_factor == 1.5

    def test_duplicate_copies_new_fields(self, temp_dataset: "DatasetDatabase"):
        """
        Test that ExportTemplate.duplicate() copies completions_per_sample and
        facet_balancing_factor to the new template.
        """
        facet = Facet.create(temp_dataset, "F7", "desc")
        temp_dataset.commit()

        original = ExportTemplate.create(
            temp_dataset,
            name="T7",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "count",
                "limit_value": 10,
                "order": "random"
            }],
            completions_per_sample=4,
            facet_balancing_factor=0.0,
        )
        temp_dataset.commit()

        copy = original.duplicate(temp_dataset)
        temp_dataset.commit()

        assert copy.completions_per_sample == 4
        assert copy.facet_balancing_factor == 0.0
        assert copy.name != original.name

    def test_normalize_completions_per_sample_integral_float(self):
        """
        Test that _normalize_completions_per_sample accepts integral floats (e.g. 3.0).
        """
        assert ExportTemplate._normalize_completions_per_sample(3.0) == 3  # type: ignore[arg-type]

    def test_normalize_completions_per_sample_rejects_non_integral_float(self):
        """
        Test that _normalize_completions_per_sample rejects non-integral floats (e.g. 3.7).
        """
        with pytest.raises(ValueError, match="must be an integer"):
            ExportTemplate._normalize_completions_per_sample(3.7)  # type: ignore[arg-type]

    def test_normalize_completions_per_sample_rejects_bool(self):
        """
        Test that _normalize_completions_per_sample rejects booleans (bool is a subclass of int).
        """
        with pytest.raises(ValueError, match="must be an integer"):
            ExportTemplate._normalize_completions_per_sample(True)  # type: ignore[arg-type]

    def test_normalize_completions_per_sample_invalid_type(self):
        """
        Test that _normalize_completions_per_sample raises ValueError on non-numeric input.
        """
        with pytest.raises(ValueError, match="must be an integer"):
            ExportTemplate._normalize_completions_per_sample("abc")  # type: ignore[arg-type]

    def test_normalize_facet_balancing_factor_rejects_nan(self):
        """
        Test that _normalize_facet_balancing_factor rejects NaN.
        """
        with pytest.raises(ValueError, match="finite"):
            ExportTemplate._normalize_facet_balancing_factor(float("nan"))

    def test_normalize_facet_balancing_factor_rejects_infinity(self):
        """
        Test that _normalize_facet_balancing_factor rejects positive infinity.
        """
        with pytest.raises(ValueError, match="finite"):
            ExportTemplate._normalize_facet_balancing_factor(float("inf"))

    def test_normalize_facet_balancing_factor_invalid_type(self):
        """
        Test that _normalize_facet_balancing_factor raises ValueError on non-numeric input.
        """
        with pytest.raises(ValueError, match="must be a number"):
            ExportTemplate._normalize_facet_balancing_factor("bad")  # type: ignore[arg-type]


# ===========================================================================
# ExportController – multiple completions per sample
# ===========================================================================


class TestMultipleCompletionsSftExport:
    """
    Tests for ExportController._run_sft_export with completions_per_sample != 1.
    """

    def test_single_completion_classic_behavior(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        With completions_per_sample=1 (default), exactly one conversation is exported per
        eligible sample — same as the legacy single-best behavior.
        """
        model_id = app_with_dataset.providers_manager.get_mock_model().model_id
        prompt_text = f"{FLAT_PREFIX_USER}What is 2+2?"

        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=1)
        # Override prompt text to use flat prefix format
        prompt_rev.prompt_text = prompt_text
        temp_dataset.commit()

        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=8, text="Four.")
        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=6, text="2+2=4.")

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=1)

        controller, entries, path = _run_export_and_load(app_with_dataset, temp_dataset, template, model_id)
        try:
            # Only 1 conversation for 1 sample despite 2 eligible completions
            assert len(entries) == 1
            assert controller.export_results.total_exported == 1
        finally:
            path.unlink(missing_ok=True)

    def test_two_completions_per_sample(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        With completions_per_sample=2 and a sample having exactly 2 eligible completions,
        2 conversation entries should be exported (one per completion, highest-rated first).
        No partial-coverage tracking is needed.
        """
        model_id = app_with_dataset.providers_manager.get_mock_model().model_id
        prompt_text = f"{FLAT_PREFIX_USER}Tell me a joke."

        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=1)
        prompt_rev.prompt_text = prompt_text
        temp_dataset.commit()

        comp_a = _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=9, text="Joke A")
        comp_b = _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=7, text="Joke B")

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=2)

        controller, entries, path = _run_export_and_load(app_with_dataset, temp_dataset, template, model_id)
        try:
            assert len(entries) == 2
            assert controller.export_results.total_exported == 2

            # First entry must use the higher-rated completion (rating 9 = "Joke A")
            first_texts = [m["value"] for m in entries[0]["conversations"] if m["from"] == "gpt"]
            second_texts = [m["value"] for m in entries[1]["conversations"] if m["from"] == "gpt"]
            assert first_texts == [comp_a.completion_text]
            assert second_texts == [comp_b.completion_text]

            # No partial coverage for this sample
            facet_summary = controller.export_results.facet_summaries[0]
            assert len(facet_summary.partial_completion_samples) == 0
        finally:
            path.unlink(missing_ok=True)

    def test_k_greater_than_eligible_completions(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        When completions_per_sample=3 but only 2 eligible completions exist, exactly 2
        conversations should be exported (never more than the eligible count) and the
        sample should appear in partial_completion_samples.
        """
        model_id = app_with_dataset.providers_manager.get_mock_model().model_id
        prompt_text = f"{FLAT_PREFIX_USER}What color is the sky?"

        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=1)
        prompt_rev.prompt_text = prompt_text
        temp_dataset.commit()

        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=8, text="Blue")
        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=6, text="Light blue")
        # Third completion intentionally omitted so K=3 > M=2

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=3)

        controller, entries, path = _run_export_and_load(app_with_dataset, temp_dataset, template, model_id)
        try:
            # Only 2 conversations even though K=3
            assert len(entries) == 2
            assert controller.export_results.total_exported == 2

            # Sample appears in partial_completion_samples
            facet_summary = controller.export_results.facet_summaries[0]
            assert len(facet_summary.partial_completion_samples) == 1
            sample_info, available_count, requested_count = facet_summary.partial_completion_samples[0]
            assert available_count == 2
            assert requested_count == 3
            assert sample_info.sample_title == "Test Sample"
        finally:
            path.unlink(missing_ok=True)

    def test_multiple_samples_multiple_completions(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        With 2 samples each having 3 eligible completions and completions_per_sample=2,
        the total exported count should be 4 (2 per sample).
        """
        from py_fade.dataset.sample import Sample  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.prompt import PromptRevision  # pylint: disable=import-outside-toplevel

        model_id = app_with_dataset.providers_manager.get_mock_model().model_id
        facet = Facet.create(temp_dataset, "MF", "multi-sample test facet", min_rating=1)
        temp_dataset.commit()

        # Sample 1
        pr1 = PromptRevision.get_or_create(temp_dataset, f"{FLAT_PREFIX_USER}Sample 1 prompt", 2048, 512)
        Sample.create_if_unique(temp_dataset, "Sample 1", pr1, "grp")
        temp_dataset.commit()
        for i in range(3):
            _add_completion(temp_dataset, pr1, model_id, facet, rating=8 - i, text=f"S1C{i}")

        # Sample 2
        pr2 = PromptRevision.get_or_create(temp_dataset, f"{FLAT_PREFIX_USER}Sample 2 prompt", 2048, 512)
        Sample.create_if_unique(temp_dataset, "Sample 2", pr2, "grp")
        temp_dataset.commit()
        for i in range(3):
            _add_completion(temp_dataset, pr2, model_id, facet, rating=7 - i, text=f"S2C{i}")

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=2, name="MultiSample")

        controller, entries, path = _run_export_and_load(app_with_dataset, temp_dataset, template, model_id)
        try:
            assert len(entries) == 4
            assert controller.export_results.total_exported == 4
            # No partial coverage; each sample has 3 eligible, we requested 2
            facet_summary = controller.export_results.facet_summaries[0]
            assert len(facet_summary.partial_completion_samples) == 0
        finally:
            path.unlink(missing_ok=True)

    def test_facet_balancing_factor_nonzero_raises(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Attempting to run SFT export with facet_balancing_factor > 0 should raise
        NotImplementedError because that feature is reserved for future implementation.
        """
        model_id = app_with_dataset.providers_manager.get_mock_model().model_id

        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=1)
        prompt_rev.prompt_text = f"{FLAT_PREFIX_USER}Hello"
        temp_dataset.commit()
        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=8, text="Hi")

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=1, facet_balancing_factor=0.5, name="BalancedTemplate")

        controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template, target_model_id=model_id)
        try:
            with pytest.raises(NotImplementedError, match="facet_balancing_factor"):
                controller.run_export()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_ordering_top_rated_first(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        When completions_per_sample=3, the 3 returned conversations should correspond
        to the top-3 rated completions in descending order.
        """
        model_id = app_with_dataset.providers_manager.get_mock_model().model_id
        prompt_text = f"{FLAT_PREFIX_USER}Order test"

        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=1)
        prompt_rev.prompt_text = prompt_text
        temp_dataset.commit()

        # Add 4 completions with ratings 5, 10, 7, 9 - top-3 by rating should be 10, 9, 7
        _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=5, text="rating5")
        comp10 = _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=10, text="rating10")
        comp7 = _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=7, text="rating7")
        comp9 = _add_completion(temp_dataset, prompt_rev, model_id, facet, rating=9, text="rating9")

        template = _make_sft_template(temp_dataset, facet, completions_per_sample=3, name="OrderTest")

        _, entries, path = _run_export_and_load(app_with_dataset, temp_dataset, template, model_id)
        try:
            assert len(entries) == 3

            assistant_texts = [next(m["value"] for m in e["conversations"] if m["from"] == "gpt") for e in entries]
            assert assistant_texts[0] == comp10.completion_text
            assert assistant_texts[1] == comp9.completion_text
            assert assistant_texts[2] == comp7.completion_text
        finally:
            path.unlink(missing_ok=True)


# ===========================================================================
# FacetExportSummary dataclass
# ===========================================================================


class TestFacetExportSummaryPartialField:
    """
    Tests for the new partial_completion_samples field on FacetExportSummary.
    """

    def test_partial_completion_samples_default_empty(self):
        """
        FacetExportSummary.partial_completion_samples should default to empty list.
        """
        summary = FacetExportSummary(facet_id=1, facet_name="Test")
        assert not summary.partial_completion_samples

    def test_partial_completion_samples_can_append(self):
        """
        Items can be appended to partial_completion_samples in the expected format.
        """
        from py_fade.controllers.export_controller import SampleExportInfo  # pylint: disable=import-outside-toplevel

        summary = FacetExportSummary(facet_id=1, facet_name="Test")
        info = SampleExportInfo(sample_id=42, sample_title="S", group_path="g")
        summary.partial_completion_samples.append((info, 1, 3))

        assert len(summary.partial_completion_samples) == 1
        stored_info, eligible, requested = summary.partial_completion_samples[0]
        assert stored_info.sample_id == 42
        assert eligible == 1
        assert requested == 3


# ===========================================================================
# Schema migration
# ===========================================================================


class TestSchemaMigration:
    """
    Tests for the schema migration that adds completions_per_sample and
    facet_balancing_factor to the export_templates table in existing databases.
    """

    def test_migration_adds_columns_to_existing_db(self, tmp_path):
        """
        When an existing database was created without completions_per_sample /
        facet_balancing_factor, DatasetDatabase.initialize() should add those columns
        so the database opens without errors.
        """
        import sqlite3  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.dataset import DatasetDatabase  # pylint: disable=import-outside-toplevel

        db_path = tmp_path / "old_schema.db"

        # Create the database using a raw SQLite connection to simulate an older
        # database that was created before the new columns were added.
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE export_templates (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                date_created DATETIME NOT NULL,
                model_family TEXT NOT NULL,
                filename_template TEXT NOT NULL,
                output_format TEXT NOT NULL,
                training_type TEXT NOT NULL,
                facets_json TEXT NOT NULL,
                normalize_style INTEGER NOT NULL,
                encrypt INTEGER NOT NULL,
                encryption_password TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Initialize the dataset — this must run the migration without raising.
        dataset = DatasetDatabase(str(db_path))
        dataset.initialize()

        # The new columns must now exist.
        conn = sqlite3.connect(str(db_path))
        result = conn.execute("PRAGMA table_info(export_templates)").fetchall()
        conn.close()
        column_names = {row[1] for row in result}

        assert "completions_per_sample" in column_names
        assert "facet_balancing_factor" in column_names

        dataset.dispose()

    def test_migration_is_idempotent_on_fresh_db(self, temp_dataset: "DatasetDatabase"):
        """
        Running initialize() (and thus the migration) on a fresh database should not
        cause errors — the columns already exist and the migration is a no-op.
        """
        # If this doesn't raise, the migration is idempotent.
        temp_dataset.initialize()


# ===========================================================================
# Display name formatting
# ===========================================================================


class TestFormatSampleDisplayName:
    """
    Tests for the _format_sample_display_name helper in WindowExportWizard.
    """

    def test_group_path_present(self):
        """
        When group_path is set, display name is 'group_path/sample_title'.
        """
        from py_fade.gui.window_export_wizard import ExportWizard  # pylint: disable=import-outside-toplevel
        from py_fade.controllers.export_controller import SampleExportInfo  # pylint: disable=import-outside-toplevel

        info = SampleExportInfo(sample_id=1, sample_title="My Sample", group_path="my_group")
        assert ExportWizard._format_sample_display_name(info) == "my_group/My Sample"

    def test_group_path_none(self):
        """
        When group_path is None, display name is just 'sample_title' — no leading slash.
        """
        from py_fade.gui.window_export_wizard import ExportWizard  # pylint: disable=import-outside-toplevel
        from py_fade.controllers.export_controller import SampleExportInfo  # pylint: disable=import-outside-toplevel

        info = SampleExportInfo(sample_id=2, sample_title="Root Sample", group_path=None)
        assert ExportWizard._format_sample_display_name(info) == "Root Sample"

    def test_group_path_empty_string(self):
        """
        When group_path is an empty string, display name is just 'sample_title'.
        """
        from py_fade.gui.window_export_wizard import ExportWizard  # pylint: disable=import-outside-toplevel
        from py_fade.controllers.export_controller import SampleExportInfo  # pylint: disable=import-outside-toplevel

        info = SampleExportInfo(sample_id=3, sample_title="Root Sample 2", group_path="")
        assert ExportWizard._format_sample_display_name(info) == "Root Sample 2"
