"""
Full Cycle Test for Facet Backup Feature.

This test validates the complete end-to-end workflow:
1. Generate test data (facet, samples, completions, ratings)
2. Export to facet backup JSON file
3. Import backup into fresh database
4. Validate semantic equivalency (excluding ID values)
5. Test round-trip consistency (export -> import -> export)

This is a comprehensive integration test that exercises all components
of the facet backup feature together.
"""

from __future__ import annotations

import tempfile
import pathlib
from typing import TYPE_CHECKING

from py_fade.controllers.import_controller import ImportController
from py_fade.controllers.export_controller import ExportController
from py_fade.data_formats.facet_backup import FacetBackupFormat
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from tests.helpers.facet_backup_helpers import (create_temp_database, create_temp_backup_file, create_test_facet_with_data,
                                                export_facet_to_backup, import_facet_from_backup)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


class TestFacetBackupFullCycle:
    """Test complete facet backup workflow from generation to round-trip consistency."""

    def test_facet_backup_full_cycle_basic(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test complete round-trip cycle with basic data."""
        # Step 1: Generate test data in source database
        self._create_test_data_basic(temp_dataset)

        # Step 2: Export to facet backup
        source_facet = Facet.get_by_name(temp_dataset, "Full Cycle Test Facet")
        assert source_facet is not None

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            backup_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(backup_path)
            export_count = export_controller.export_facet_backup(source_facet.id)
            assert export_count == 1
            assert backup_path.exists()

            # Step 3: Import backup into fresh database
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
                target_db_path = pathlib.Path(db_file.name)

            try:
                from py_fade.dataset.dataset import DatasetDatabase
                target_dataset = DatasetDatabase(target_db_path)
                target_dataset.initialize()

                import_controller = ImportController(app_with_dataset, target_dataset)
                import_controller.add_source(backup_path)
                import_count = import_controller.import_facet_backup_to_dataset()
                assert import_count == 4  # facet + sample + completion + rating

                # Step 4: Validate semantic equivalency
                self._validate_semantic_equivalency_basic(temp_dataset, target_dataset)

                # Step 5: Test round-trip consistency
                self._test_round_trip_consistency(app_with_dataset, target_dataset, source_facet.name)

                target_dataset.dispose()

            finally:
                target_db_path.unlink(missing_ok=True)

        finally:
            backup_path.unlink(missing_ok=True)

    def test_facet_backup_full_cycle_complex(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test complete round-trip cycle with complex data (multiple samples, completions, ratings)."""
        # Step 1: Generate complex test data
        self._create_test_data_complex(temp_dataset)

        # Step 2: Export to facet backup
        source_facet = Facet.get_by_name(temp_dataset, "Complex Cycle Test Facet")
        assert source_facet is not None

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            backup_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(backup_path)
            export_count = export_controller.export_facet_backup(source_facet.id)
            assert export_count == 1

            # Step 3: Import backup into fresh database
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
                target_db_path = pathlib.Path(db_file.name)

            try:
                from py_fade.dataset.dataset import DatasetDatabase
                target_dataset = DatasetDatabase(target_db_path)
                target_dataset.initialize()

                import_controller = ImportController(app_with_dataset, target_dataset)
                import_controller.add_source(backup_path)
                import_count = import_controller.import_facet_backup_to_dataset()

                # Expect: 1 facet + 3 samples + 6 completions + 6 ratings = 16 items
                assert import_count == 16

                # Step 4: Validate semantic equivalency
                self._validate_semantic_equivalency_complex(temp_dataset, target_dataset)

                # Step 5: Test round-trip consistency
                self._test_round_trip_consistency(app_with_dataset, target_dataset, source_facet.name)

                target_dataset.dispose()

            finally:
                target_db_path.unlink(missing_ok=True)

        finally:
            backup_path.unlink(missing_ok=True)

    def test_facet_backup_multiple_imports_idempotent(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test that importing the same backup multiple times is idempotent."""
        # Create test data
        self._create_test_data_basic(temp_dataset)
        source_facet = Facet.get_by_name(temp_dataset, "Full Cycle Test Facet")

        # Export to backup
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            backup_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app_with_dataset, temp_dataset)
            export_controller.set_output_path(backup_path)
            export_controller.export_facet_backup(source_facet.id)

            # Create target database
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
                target_db_path = pathlib.Path(db_file.name)

            try:
                from py_fade.dataset.dataset import DatasetDatabase
                target_dataset = DatasetDatabase(target_db_path)
                target_dataset.initialize()

                # First import
                import_controller1 = ImportController(app_with_dataset, target_dataset)
                import_controller1.add_source(backup_path)
                first_count = import_controller1.import_facet_backup_to_dataset()

                # Get initial counts
                initial_facet_count = len(Facet.get_all(target_dataset))
                initial_sample_count = len(target_dataset.session.query(Sample).all())
                initial_completion_count = len(target_dataset.session.query(PromptCompletion).all())
                initial_rating_count = len(target_dataset.session.query(PromptCompletionRating).all())

                # Second import (should be idempotent)
                import_controller2 = ImportController(app_with_dataset, target_dataset)
                import_controller2.add_source(backup_path)
                second_count = import_controller2.import_facet_backup_to_dataset("skip_duplicates")

                # Verify no additional items were created
                assert second_count == 0  # Nothing new imported
                assert len(Facet.get_all(target_dataset)) == initial_facet_count
                assert len(target_dataset.session.query(Sample).all()) == initial_sample_count
                assert len(target_dataset.session.query(PromptCompletion).all()) == initial_completion_count
                assert len(target_dataset.session.query(PromptCompletionRating).all()) == initial_rating_count

                target_dataset.dispose()

            finally:
                target_db_path.unlink(missing_ok=True)

        finally:
            backup_path.unlink(missing_ok=True)

    def _create_test_data_basic(self, dataset: "DatasetDatabase") -> None:
        """Create basic test data: 1 facet, 1 sample, 1 completion, 1 rating."""
        create_test_facet_with_data(dataset, "Full Cycle Test Facet", "Facet for full cycle testing")

    def _create_test_data_complex(self, dataset: "DatasetDatabase") -> None:
        """Create complex test data: 1 facet, 3 samples, 6 completions, 6 ratings."""
        create_test_facet_with_data(dataset, "Complex Cycle Test Facet", "Complex facet for full cycle testing", sample_count=3,
                                    completions_per_sample=2)

        for i in range(3):
            prompt_rev = PromptRevision.get_or_create(dataset, f"Complex cycle prompt {i}", 2048, 512)

            sample = Sample.create_if_unique(dataset, f"Complex Cycle Sample {i}", prompt_rev, f"complex_cycle_{i}")

            # Create 2 completions per sample
            for j in range(2):
                import hashlib
                completion_text = f"Complex cycle completion {i}-{j}"
                sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()

                completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=f"complex-cycle-model-{j}",
                                              temperature=0.6 + j * 0.1, top_k=35 + j * 5, completion_text=completion_text, tags={
                                                  "complex": True,
                                                  "index": i
                                              }, prefill=None, beam_token=None, is_truncated=False, context_length=2048, max_tokens=512)
                dataset.session.add(completion)

    def _validate_semantic_equivalency_basic(self, source_dataset: "DatasetDatabase", target_dataset: "DatasetDatabase") -> None:
        """Validate that basic data was imported with semantic equivalency."""
        # Validate facet
        source_facet = Facet.get_by_name(source_dataset, "Full Cycle Test Facet")
        target_facet = Facet.get_by_name(target_dataset, "Full Cycle Test Facet")

        assert source_facet is not None
        assert target_facet is not None
        assert source_facet.name == target_facet.name
        assert source_facet.description == target_facet.description
        # IDs will be different, which is expected

        # Validate samples
        source_samples = source_dataset.session.query(Sample).all()
        target_samples = target_dataset.session.query(Sample).all()

        assert len(source_samples) == 1
        assert len(target_samples) == 1
        assert source_samples[0].title == target_samples[0].title
        assert source_samples[0].group_path == target_samples[0].group_path

        # Validate prompt revisions
        assert source_samples[0].prompt_revision.prompt_text == target_samples[0].prompt_revision.prompt_text
        assert source_samples[0].prompt_revision.context_length == target_samples[0].prompt_revision.context_length
        assert source_samples[0].prompt_revision.max_tokens == target_samples[0].prompt_revision.max_tokens

        # Validate completions
        source_completions = source_dataset.session.query(PromptCompletion).all()
        target_completions = target_dataset.session.query(PromptCompletion).all()

        assert len(source_completions) == 1
        assert len(target_completions) == 1
        assert source_completions[0].completion_text == target_completions[0].completion_text
        assert source_completions[0].model_id == target_completions[0].model_id
        assert source_completions[0].temperature == target_completions[0].temperature
        assert source_completions[0].top_k == target_completions[0].top_k
        assert source_completions[0].tags == target_completions[0].tags

        # Validate ratings
        source_ratings = source_dataset.session.query(PromptCompletionRating).all()
        target_ratings = target_dataset.session.query(PromptCompletionRating).all()

        assert len(source_ratings) == 1
        assert len(target_ratings) == 1
        assert source_ratings[0].rating == target_ratings[0].rating

    def _validate_semantic_equivalency_complex(self, source_dataset: "DatasetDatabase", target_dataset: "DatasetDatabase") -> None:
        """Validate that complex data was imported with semantic equivalency."""
        # Validate facet
        source_facet = Facet.get_by_name(source_dataset, "Complex Cycle Test Facet")
        target_facet = Facet.get_by_name(target_dataset, "Complex Cycle Test Facet")

        assert source_facet is not None
        assert target_facet is not None
        assert source_facet.name == target_facet.name
        assert source_facet.description == target_facet.description

        # Validate counts
        source_samples = source_dataset.session.query(Sample).all()
        target_samples = target_dataset.session.query(Sample).all()
        source_completions = source_dataset.session.query(PromptCompletion).all()
        target_completions = target_dataset.session.query(PromptCompletion).all()
        source_ratings = source_dataset.session.query(PromptCompletionRating).all()
        target_ratings = target_dataset.session.query(PromptCompletionRating).all()

        assert len(source_samples) == len(target_samples) == 3
        assert len(source_completions) == len(target_completions) == 6
        assert len(source_ratings) == len(target_ratings) == 6

        # Validate sample titles (order may differ)
        source_titles = sorted([s.title for s in source_samples])
        target_titles = sorted([s.title for s in target_samples])
        assert source_titles == target_titles

        # Validate completion model IDs
        source_model_ids = sorted([c.model_id for c in source_completions])
        target_model_ids = sorted([c.model_id for c in target_completions])
        assert source_model_ids == target_model_ids

        # Validate rating values
        source_rating_values = sorted([r.rating for r in source_ratings])
        target_rating_values = sorted([r.rating for r in target_ratings])
        assert source_rating_values == target_rating_values

    def _test_round_trip_consistency(self, app: "pyFadeApp", dataset: "DatasetDatabase", facet_name: str) -> None:
        """Test that exporting imported data produces equivalent backup."""
        facet = Facet.get_by_name(dataset, facet_name)
        assert facet is not None

        # Export the imported facet
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            round_trip_path = pathlib.Path(f.name)

        try:
            export_controller = ExportController.create_for_facet_backup(app, dataset)
            export_controller.set_output_path(round_trip_path)
            export_controller.export_facet_backup(facet.id)

            # Load and validate the round-trip backup
            backup_format = FacetBackupFormat(round_trip_path)
            backup_format.load()

            backup_data = backup_format.backup_data
            assert backup_data is not None
            assert backup_data.facet['name'] == facet_name

            # The backup should contain the same data structure (counts may be verified)
            # IDs will be different from original, but semantic content should be equivalent
            assert len(backup_data.samples) >= 1
            assert len(backup_data.completions) >= 1
            assert len(backup_data.ratings) >= 1

            # Validate basic structure integrity
            assert backup_data.pyfade_version is not None
            assert backup_data.format_version == 1
            assert backup_data.export_timestamp is not None

        finally:
            round_trip_path.unlink(missing_ok=True)
