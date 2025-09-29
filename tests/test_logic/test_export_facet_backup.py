"""
Test Facet Backup export functionality in ExportController.

Tests the export of facet backup files with complete facet data.
"""

from __future__ import annotations

import tempfile
import pathlib
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.export_controller import ExportController
from py_fade.data_formats.facet_backup import FacetBackupFormat
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


class TestFacetBackupExport:
    """Test facet backup export functionality."""

    def test_create_export_controller_for_facet_backup(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test creating ExportController specifically for facet backup."""
        export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)

        assert export_controller.app == app_with_dataset
        assert export_controller.dataset == temp_dataset
        assert export_controller.export_template is None
        assert export_controller.output_path is None

    def test_export_facet_backup_basic(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test basic facet backup export."""
        # Create test data
        facet = Facet.create(temp_dataset, "Export Test Facet", "Facet for export testing")
        temp_dataset.commit()

        prompt_rev = PromptRevision.get_or_create(temp_dataset, "Export test prompt", 2048, 512)
        temp_dataset.commit()

        sample = Sample.create_if_unique(temp_dataset, "Export Test Sample", prompt_rev, "export_test")
        temp_dataset.commit()

        # Create completion
        import hashlib
        completion_text = "Export test completion"
        sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

        completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id="export-test-model", temperature=0.9,
                                      top_k=30, completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                      context_length=2048, max_tokens=512)
        temp_dataset.session.add(completion)
        temp_dataset.commit()

        rating = PromptCompletionRating.set_rating(temp_dataset, completion, facet, 9)
        temp_dataset.commit()

        # Export facet backup
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(temp_path)

            exported_count = export_controller.export_facet_backup(facet.id)
            assert exported_count == 1

            # Verify the backup file was created
            assert temp_path.exists()

            # Verify the backup content by loading it
            backup_format = FacetBackupFormat(temp_path)
            backup_format.load()

            backup_data = backup_format.backup_data
            assert backup_data is not None
            assert backup_data.facet['name'] == "Export Test Facet"
            assert backup_data.facet['description'] == "Facet for export testing"
            assert len(backup_data.samples) == 1
            assert len(backup_data.completions) == 1
            assert len(backup_data.ratings) == 1

            # Verify sample data
            sample_data = backup_data.samples[0]
            assert sample_data['title'] == "Export Test Sample"
            assert sample_data['group_path'] == "export_test"
            assert sample_data['prompt_revision']['prompt_text'] == "Export test prompt"

            # Verify completion data
            completion_data = backup_data.completions[0]
            assert completion_data['completion_text'] == "Export test completion"
            assert completion_data['model_id'] == "export-test-model"
            assert completion_data['temperature'] == 0.9
            assert completion_data['top_k'] == 30

            # Verify rating data
            rating_data = backup_data.ratings[0]
            assert rating_data['rating'] == 9
            assert rating_data['facet_id'] == facet.id

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_facet_backup_empty_facet(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test exporting a facet with no associated data."""
        # Create empty facet
        facet = Facet.create(temp_dataset, "Empty Test Facet", "Empty facet for testing")
        temp_dataset.commit()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(temp_path)

            exported_count = export_controller.export_facet_backup(facet.id)
            assert exported_count == 1

            # Verify the backup content
            backup_format = FacetBackupFormat(temp_path)
            backup_format.load()

            backup_data = backup_format.backup_data
            assert backup_data is not None
            assert backup_data.facet['name'] == "Empty Test Facet"
            assert len(backup_data.samples) == 0
            assert len(backup_data.completions) == 0
            assert len(backup_data.ratings) == 0
            assert len(backup_data.tags) == 0

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_facet_backup_nonexistent_facet(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test error handling when exporting nonexistent facet."""
        export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller.set_output_path(temp_path)

            with pytest.raises(ValueError, match="Facet with ID 9999 not found"):
                export_controller.export_facet_backup(9999)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_facet_backup_no_output_path(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test error handling when output path is not set."""
        facet = Facet.create(temp_dataset, "No Path Test Facet", "Test no output path")
        temp_dataset.commit()

        export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)

        with pytest.raises(ValueError, match="Output path must be set"):
            export_controller.export_facet_backup(facet.id)

    def test_export_facet_backup_no_session(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test error handling when dataset session is not initialized."""
        facet = Facet.create(temp_dataset, "No Session Test Facet", "Test no session")
        temp_dataset.commit()

        # Store facet ID before disposing
        facet_id = facet.id

        # Dispose the session
        temp_dataset.dispose()

        export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller.set_output_path(temp_path)

            with pytest.raises(RuntimeError, match="Dataset session is not initialized"):
                export_controller.export_facet_backup(facet_id)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_facet_backup_multiple_samples_completions(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test exporting a facet with multiple samples and completions."""
        facet = Facet.create(temp_dataset, "Multi Test Facet", "Facet with multiple items")
        temp_dataset.commit()

        # Create multiple samples and completions
        samples = []
        completions = []

        for i in range(3):
            prompt_rev = PromptRevision.get_or_create(temp_dataset, f"Multi test prompt {i}", 2048, 512)
            temp_dataset.commit()

            sample = Sample.create_if_unique(temp_dataset, f"Multi Test Sample {i}", prompt_rev, f"multi_test_{i}")
            temp_dataset.commit()
            samples.append(sample)

            # Create 2 completions per sample
            for j in range(2):
                import hashlib
                completion_text = f"Multi test completion {i}-{j}"
                sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

                completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=f"multi-test-model-{j}",
                                              temperature=0.5 + j * 0.1, top_k=40 + j * 10, completion_text=completion_text, tags={},
                                              prefill=None, beam_token=None, is_truncated=False, context_length=2048, max_tokens=512)
                temp_dataset.session.add(completion)
                temp_dataset.commit()

                # Add rating for this completion
                PromptCompletionRating.set_rating(temp_dataset, completion, facet, 5 + j)
                completions.append(completion)

        temp_dataset.commit()

        # Export the facet backup
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(temp_path)

            exported_count = export_controller.export_facet_backup(facet.id)
            assert exported_count == 1

            # Verify the backup content
            backup_format = FacetBackupFormat(temp_path)
            backup_format.load()

            backup_data = backup_format.backup_data
            assert backup_data is not None
            assert backup_data.facet['name'] == "Multi Test Facet"
            assert len(backup_data.samples) == 3
            assert len(backup_data.completions) == 6  # 3 samples * 2 completions each
            assert len(backup_data.ratings) == 6  # One rating per completion

            # Verify sample titles are correct
            sample_titles = [s['title'] for s in backup_data.samples]
            expected_titles = [f"Multi Test Sample {i}" for i in range(3)]
            assert sorted(sample_titles) == sorted(expected_titles)

            # Verify completion model IDs
            model_ids = [c['model_id'] for c in backup_data.completions]
            expected_model_ids = [f"multi-test-model-{j}" for i in range(3) for j in range(2)]
            assert sorted(model_ids) == sorted(expected_model_ids)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_template_based_export_still_works(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test that existing template-based export functionality is not broken."""
        # Create test data
        facet = Facet.create(temp_dataset, "Template Test Facet", "For template export testing")
        temp_dataset.commit()

        # Use the helper to create test template
        from tests.helpers.export_wizard_helpers import create_test_template
        _, template = create_test_template(temp_dataset)

        # Test that ExportController can still be created with a template
        export_controller = ExportController(app_with_dataset, temp_dataset, template)

        assert export_controller.export_template == template
        assert export_controller.export_template is not None

        # Test that run_export requires a template
        with pytest.raises(ValueError, match="Export template must be set"):
            no_template_controller = ExportController(app_with_dataset, temp_dataset, None)
            no_template_controller.set_output_path(pathlib.Path("/tmp/test.jsonl"))
            no_template_controller.run_export()
