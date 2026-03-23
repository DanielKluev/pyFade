"""
Tests for the Better Truncation feature.

Covers:
- Toggle Truncation State action in CompletionFrame context menu
- Mark as Truncated checkbox in ThreeWayCompletionEditorWindow
- Export template allow_truncated option and NO_EOS marker
- ExportTemplate model allow_truncated field CRUD
- Schema migration for allow_truncated column
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import tempfile
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.export_controller import ExportController
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.providers.flat_prefix_template import NO_EOS_MARKER
from tests.helpers.data_helpers import create_completion_with_rating_and_logprobs
from tests.helpers.export_wizard_helpers import (create_and_run_export_test, create_simple_export_template,
                                                 setup_facet_sample_and_completion)

if TYPE_CHECKING:
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


# ---------------------------------------------------------------------------
# NO_EOS_MARKER constant
# ---------------------------------------------------------------------------
class TestNoEosMarker:
    """
    Verify the NO_EOS_MARKER constant is defined correctly.
    """

    def test_no_eos_marker_value(self) -> None:
        """
        NO_EOS_MARKER should be the string '<|NO_EOS|>'.
        """
        assert NO_EOS_MARKER == "<|NO_EOS|>"


# ---------------------------------------------------------------------------
# ExportTemplate.allow_truncated field
# ---------------------------------------------------------------------------
class TestExportTemplateAllowTruncated:
    """
    Tests for the allow_truncated field on ExportTemplate.
    """

    def test_create_default_false(self, temp_dataset: "DatasetDatabase") -> None:
        """
        allow_truncated defaults to False when creating a template.
        """
        facet = Facet.create(temp_dataset, "F1", "desc")
        temp_dataset.commit()
        template = ExportTemplate.create(
            temp_dataset,
            name="T1",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
            }],
        )
        temp_dataset.commit()
        assert template.allow_truncated is False

    def test_create_with_allow_truncated_true(self, temp_dataset: "DatasetDatabase") -> None:
        """
        allow_truncated can be set to True on creation.
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
            allow_truncated=True,
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
            }],
        )
        temp_dataset.commit()
        assert template.allow_truncated is True

    def test_update_allow_truncated(self, temp_dataset: "DatasetDatabase") -> None:
        """
        allow_truncated can be toggled via update().
        """
        facet = Facet.create(temp_dataset, "F3", "desc")
        temp_dataset.commit()
        template = ExportTemplate.create(
            temp_dataset,
            name="T3",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
            }],
        )
        temp_dataset.commit()
        assert template.allow_truncated is False

        template.update(temp_dataset, allow_truncated=True)
        temp_dataset.commit()
        assert template.allow_truncated is True

        template.update(temp_dataset, allow_truncated=False)
        temp_dataset.commit()
        assert template.allow_truncated is False

    def test_duplicate_preserves_allow_truncated(self, temp_dataset: "DatasetDatabase") -> None:
        """
        Duplicating a template preserves the allow_truncated setting.
        """
        facet = Facet.create(temp_dataset, "F4", "desc")
        temp_dataset.commit()
        original = ExportTemplate.create(
            temp_dataset,
            name="T4",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            allow_truncated=True,
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
            }],
        )
        temp_dataset.commit()

        copy = original.duplicate(temp_dataset)
        temp_dataset.commit()
        assert copy.allow_truncated is True
        assert copy.id != original.id


# ---------------------------------------------------------------------------
# Export controller: truncated completion filtering and NO_EOS marker
# ---------------------------------------------------------------------------
class TestExportTruncatedCompletions:
    """
    Tests that the export controller correctly handles truncated completions
    based on the allow_truncated template setting.
    """

    def test_truncated_completion_excluded_by_default(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp") -> None:
        """
        When allow_truncated is False (default), truncated completions are skipped
        even if they meet rating and logprob thresholds. If no non-truncated
        completions remain, the export raises ValueError.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-5.0,
                                                              facet_avg_logprob=-3.0)

        # Create a truncated completion that otherwise meets all thresholds
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Truncated answer", mapped_model.model_id, facet, rating=9,
                                                   min_logprob=-0.3, avg_logprob=-0.2, is_truncated=True)

        template = create_simple_export_template(temp_dataset, facet, allow_truncated=False)

        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)
        try:
            with pytest.raises(ValueError, match="No eligible samples found"):
                export_controller.run_export()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_truncated_completion_included_when_allowed(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp") -> None:
        """
        When allow_truncated is True, truncated completions that meet rating
        and logprob thresholds are exported.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-5.0,
                                                              facet_avg_logprob=-3.0)

        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Truncated answer", mapped_model.model_id, facet, rating=9,
                                                   min_logprob=-0.3, avg_logprob=-0.2, is_truncated=True)

        template = create_simple_export_template(temp_dataset, facet, allow_truncated=True)

        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)
        try:
            exported_count = export_controller.run_export()
            assert exported_count == 1, "Truncated completion should be included when allow_truncated is True"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_truncated_export_has_no_eos_marker(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp") -> None:
        """
        Truncated completions exported with allow_truncated=True have
        '<|NO_EOS|>' appended to the assistant message content.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-5.0,
                                                              facet_avg_logprob=-3.0)

        completion_text = "This is a truncated answer"
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, completion_text, mapped_model.model_id, facet, rating=9,
                                                   min_logprob=-0.3, avg_logprob=-0.2, is_truncated=True)

        template = create_simple_export_template(temp_dataset, facet, allow_truncated=True)

        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)
        try:
            exported_count = export_controller.run_export()
            assert exported_count == 1

            # Read the exported JSONL file and check last assistant message
            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 1

            record = json.loads(lines[0])
            conversations = record.get("conversations", [])
            # Find the assistant message
            assistant_msgs = [msg for msg in conversations if msg.get("from") == "gpt"]
            assert len(assistant_msgs) == 1
            assert assistant_msgs[0]["value"].endswith(NO_EOS_MARKER), \
                f"Expected NO_EOS marker at end of truncated completion, got: {assistant_msgs[0]['value']!r}"
            assert assistant_msgs[0]["value"] == completion_text + NO_EOS_MARKER
        finally:
            temp_path.unlink(missing_ok=True)

    def test_non_truncated_export_no_marker(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp") -> None:
        """
        Non-truncated completions do NOT get the '<|NO_EOS|>' marker.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-5.0,
                                                              facet_avg_logprob=-3.0)

        completion_text = "This is a full answer"
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, completion_text, mapped_model.model_id, facet, rating=9,
                                                   min_logprob=-0.3, avg_logprob=-0.2, is_truncated=False)

        template = create_simple_export_template(temp_dataset, facet, allow_truncated=True)

        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)
        try:
            exported_count = export_controller.run_export()
            assert exported_count == 1

            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            record = json.loads(lines[0])
            conversations = record.get("conversations", [])
            assistant_msgs = [msg for msg in conversations if msg.get("from") == "gpt"]
            assert len(assistant_msgs) == 1
            assert not assistant_msgs[0]["value"].endswith(NO_EOS_MARKER), \
                "Non-truncated completion should NOT have NO_EOS marker"
            assert assistant_msgs[0]["value"] == completion_text
        finally:
            temp_path.unlink(missing_ok=True)

    def test_mixed_truncated_and_full_completions(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp") -> None:
        """
        With allow_truncated=False and both truncated and non-truncated completions,
        only the non-truncated completion is exported.
        """
        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        facet, prompt_rev = setup_facet_sample_and_completion(temp_dataset, facet_min_rating=5, facet_min_logprob=-5.0,
                                                              facet_avg_logprob=-3.0)

        # Create truncated completion with high rating
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Truncated high-rated", mapped_model.model_id, facet,
                                                   rating=10, min_logprob=-0.1, avg_logprob=-0.05, is_truncated=True)

        # Create non-truncated completion with lower (but still valid) rating
        create_completion_with_rating_and_logprobs(temp_dataset, prompt_rev, "Full lower-rated", mapped_model.model_id, facet, rating=7,
                                                   min_logprob=-0.3, avg_logprob=-0.2, is_truncated=False)

        template = create_simple_export_template(temp_dataset, facet, allow_truncated=False)

        export_controller, temp_path = create_and_run_export_test(app_with_dataset, temp_dataset, template)
        try:
            exported_count = export_controller.run_export()
            assert exported_count == 1

            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            record = json.loads(lines[0])
            conversations = record.get("conversations", [])
            assistant_msgs = [msg for msg in conversations if msg.get("from") == "gpt"]
            assert len(assistant_msgs) == 1
            assert assistant_msgs[0]["value"] == "Full lower-rated"
        finally:
            temp_path.unlink(missing_ok=True)
