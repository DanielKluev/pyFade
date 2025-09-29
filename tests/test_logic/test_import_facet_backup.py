"""
Test Facet Backup import functionality in ImportController.

Tests the detection, parsing, and import of facet backup files.
"""

from __future__ import annotations

import pathlib
import tempfile
from typing import TYPE_CHECKING

import pytest

from py_fade.controllers.import_controller import ImportController
from py_fade.data_formats.facet_backup import FacetBackupFormat
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from tests.helpers.facet_backup_helpers import (create_temp_database, create_temp_backup_file, create_test_facet_with_data,
                                                export_facet_to_backup, import_facet_from_backup)

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


class TestFacetBackupImport:
    """Test facet backup import functionality."""

    def test_detect_facet_backup_format(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test that ImportController can detect facet backup format."""
        # Create a simple facet backup
        facet = Facet.create(temp_dataset, "Test Facet", "Test description")
        temp_dataset.commit()

        backup_format = FacetBackupFormat()
        backup_format.create_backup_from_facet(temp_dataset, facet)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            backup_format.set_path(temp_path)
            backup_format.save()

            # Test format detection
            import_controller = ImportController(app_with_dataset, temp_dataset)
            detected_format = import_controller.detect_format(temp_path)

            assert detected_format == "facet_backup"

        finally:
            temp_path.unlink(missing_ok=True)

    def test_add_facet_backup_source(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test adding a facet backup source to ImportController."""
        # Create a facet backup file
        facet = Facet.create(temp_dataset, "Source Test Facet", "Test adding source")
        temp_dataset.commit()

        backup_format = FacetBackupFormat()
        backup_format.create_backup_from_facet(temp_dataset, facet)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = pathlib.Path(f.name)

        try:
            backup_format.set_path(temp_path)
            backup_format.save()

            # Add source
            import_controller = ImportController(app_with_dataset, temp_dataset)
            source = import_controller.add_source(temp_path)

            # Verify source is FacetBackupFormat
            assert isinstance(source, FacetBackupFormat)
            assert len(import_controller.sources) == 1

        finally:
            temp_path.unlink(missing_ok=True)

    def test_import_facet_backup_basic(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test importing a basic facet backup into a new database."""
        # Create source data using helper
        source_facet = create_test_facet_with_data(temp_dataset, "Import Test Facet", "Facet for import testing")

        # Create backup and import to fresh database
        with create_temp_backup_file() as temp_path:
            export_facet_to_backup(app_with_dataset, temp_dataset, source_facet.id, temp_path)

            # Import backup into fresh database
            with create_temp_database() as target_dataset:
                imported_count = import_facet_from_backup(app_with_dataset, target_dataset, temp_path)
                assert imported_count > 0

                # Verify the facet was imported
                imported_facet = Facet.get_by_name(target_dataset, "Import Test Facet")
                assert imported_facet is not None
                assert imported_facet.description == "Facet for import testing"

                # Verify sample was imported
                samples = target_dataset.session.query(Sample).all()
                assert len(samples) == 1
                assert samples[0].title == "Import Test Facet Sample 0"

                # Verify completion was imported
                completions = target_dataset.session.query(PromptCompletion).all()
                assert len(completions) == 1
                assert completions[0].completion_text == "import test facet completion 0-0"
                assert completions[0].model_id == "test-model-0"

                # Verify rating was imported
                ratings = target_dataset.session.query(PromptCompletionRating).all()
                assert len(ratings) == 1
                assert ratings[0].rating == 6
                assert ratings[0].facet_id == imported_facet.id

    def test_import_facet_backup_skip_duplicates(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test importing facet backup with skip_duplicates strategy."""
        # Create source facet and backup
        source_facet = create_test_facet_with_data(temp_dataset, "Duplicate Test Facet", "Original description")

        with create_temp_backup_file() as temp_path:
            export_facet_to_backup(app_with_dataset, temp_dataset, source_facet.id, temp_path)

            # Import into fresh database
            with create_temp_database() as target_dataset:
                # First import
                first_count = import_facet_from_backup(app_with_dataset, target_dataset, temp_path)
                assert first_count == 4  # facet + sample + completion + rating

                # Second import with skip_duplicates (default)
                second_count = import_facet_from_backup(app_with_dataset, target_dataset, temp_path, "skip_duplicates")
                assert second_count == 0  # Nothing imported, facet already exists

                # Verify still only one facet
                facets = Facet.get_all(target_dataset)
                facet_names = [f.name for f in facets]
                assert facet_names.count("Duplicate Test Facet") == 1

    def test_import_facet_backup_merge_strategy(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test importing facet backup with merge strategy."""
        # Create facet with backup
        original_facet = create_test_facet_with_data(temp_dataset, "Merge Test Facet", "Updated description")

        with create_temp_backup_file() as temp_path:
            export_facet_to_backup(app_with_dataset, temp_dataset, original_facet.id, temp_path)

            # Create target database with a facet that has different description
            with create_temp_database() as target_dataset:
                # Create facet with same name but different description
                Facet.create(target_dataset, "Merge Test Facet", "Original description")
                target_dataset.commit()

                # Import with merge strategy
                imported_count = import_facet_from_backup(app_with_dataset, target_dataset, temp_path, "merge")
                assert imported_count == 4  # All items imported since target was empty initially

                # Verify description was merged from backup
                updated_facet = Facet.get_by_name(target_dataset, "Merge Test Facet")
                assert updated_facet.description == "Updated description"

    def test_import_facet_backup_error_on_conflict(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test importing facet backup with error_on_conflict strategy."""
        # Create facet and backup
        original_facet = create_test_facet_with_data(temp_dataset, "Conflict Test Facet", "Original description")

        with create_temp_backup_file() as temp_path:
            export_facet_to_backup(app_with_dataset, temp_dataset, original_facet.id, temp_path)

            # Create target database with same facet name
            with create_temp_database() as target_dataset:
                # Create facet with same name
                Facet.create(target_dataset, "Conflict Test Facet", "Existing description")
                target_dataset.commit()

                # Import with error_on_conflict strategy should raise error
                import_controller = ImportController(app_with_dataset, target_dataset)
                import_controller.add_source(temp_path)

                with pytest.raises(ValueError, match="already exists"):
                    import_controller.import_facet_backup_to_dataset("error_on_conflict")

    def test_import_facet_backup_no_backup_source(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test error handling when no facet backup source is added."""
        import_controller = ImportController(app_with_dataset, temp_dataset)

        with pytest.raises(ValueError, match="No facet backup sources found"):
            import_controller.import_facet_backup_to_dataset()

    def test_import_facet_backup_multiple_sources_error(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """Test error handling when multiple facet backup sources are added."""
        # Create two backup files
        facet1 = Facet.create(temp_dataset, "Multi Test Facet 1", "First facet")
        facet2 = Facet.create(temp_dataset, "Multi Test Facet 2", "Second facet")
        temp_dataset.commit()

        backup1 = FacetBackupFormat()
        backup1.create_backup_from_facet(temp_dataset, facet1)

        backup2 = FacetBackupFormat()
        backup2.create_backup_from_facet(temp_dataset, facet2)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f1, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f2:

            temp_path1 = pathlib.Path(f1.name)
            temp_path2 = pathlib.Path(f2.name)

        try:
            backup1.set_path(temp_path1)
            backup1.save()

            backup2.set_path(temp_path2)
            backup2.save()

            import_controller = ImportController(app_with_dataset, temp_dataset)
            import_controller.add_source(temp_path1)
            import_controller.add_source(temp_path2)

            with pytest.raises(ValueError, match="Multiple facet backup sources not supported"):
                import_controller.import_facet_backup_to_dataset()

        finally:
            temp_path1.unlink(missing_ok=True)
            temp_path2.unlink(missing_ok=True)
