"""
Test Facet Backup data format functionality.

Tests serialization/deserialization, validation, and round-trip consistency
for the Facet Backup JSON format.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import TYPE_CHECKING

import pytest

from py_fade.data_formats.facet_backup import FacetBackupFormat, FacetBackupData, FACET_BACKUP_FORMAT_VERSION, PYFADE_VERSION
from py_fade.dataset.facet import Facet
from tests.helpers.facet_backup_helpers import create_test_facet_with_data, create_temp_backup_file

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


class TestFacetBackupFormat:
    """Test the FacetBackupFormat class functionality."""

    def test_init_with_path(self):
        """Test initialization with a file path."""
        backup = FacetBackupFormat("/tmp/test.json")
        assert backup.json_file_path == pathlib.Path("/tmp/test.json")
        assert not backup.is_loaded
        assert backup.backup_data is None

    def test_init_without_path(self):
        """Test initialization without a file path."""
        backup = FacetBackupFormat()
        assert backup.json_file_path is None
        assert not backup.is_loaded
        assert backup.backup_data is None

    def test_set_path(self):
        """Test setting the file path."""
        backup = FacetBackupFormat()
        backup.set_path("/tmp/test.json")
        assert backup.json_file_path == pathlib.Path("/tmp/test.json")

    def test_set_path_warns_non_json_extension(self, caplog):
        """Test that set_path warns for non-JSON extensions."""
        backup = FacetBackupFormat()
        backup.set_path("/tmp/test.txt")
        assert "should use .json extension" in caplog.text

    def test_create_backup_from_facet_basic(self, temp_dataset: "DatasetDatabase"):
        """Test creating a basic backup from a facet."""
        # Create test facet
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet for backup")
        temp_dataset.commit()

        # Create backup format instance and generate backup
        backup = FacetBackupFormat()
        backup_data = backup.create_backup_from_facet(temp_dataset, facet)

        # Validate basic structure
        assert backup_data.pyfade_version == PYFADE_VERSION
        assert backup_data.format_version == FACET_BACKUP_FORMAT_VERSION
        assert backup_data.facet['id'] == facet.id
        assert backup_data.facet['name'] == facet.name
        assert backup_data.facet['description'] == facet.description
        assert backup_data.export_timestamp is not None

        # With no samples/completions/ratings, these should be empty
        assert len(backup_data.samples) == 0
        assert len(backup_data.completions) == 0
        assert len(backup_data.ratings) == 0
        assert len(backup_data.tags) == 0

    def test_create_backup_with_sample_and_completion(self, temp_dataset: "DatasetDatabase"):
        """
        Test creating backup with sample, completion, and rating data.

        Flow:
        1. Create facet with sample, completion, and rating using helper
        2. Create backup from facet
        3. Verify all data is correctly captured in backup

        Edge cases tested:
        - Sample with prompt revision is exported
        - Completion with model_id is exported
        - Rating with facet_id association is preserved
        """
        # Create test facet with data using helper
        facet = create_test_facet_with_data(temp_dataset, "Test Facet", "Test facet for backup")

        # Create backup
        backup = FacetBackupFormat()
        backup_data = backup.create_backup_from_facet(temp_dataset, facet)

        # Validate data was captured
        assert len(backup_data.samples) == 1
        assert len(backup_data.completions) == 1
        assert len(backup_data.ratings) == 1

        # Validate sample data
        sample_data = backup_data.samples[0]
        assert sample_data['title'] == "Test Facet Sample 0"
        assert sample_data['group_path'] == "group_0"
        assert sample_data['prompt_revision']['prompt_text'] == "test facet prompt 0"

        # Validate completion data
        completion_data = backup_data.completions[0]
        assert completion_data['completion_text'] == "test facet completion 0-0"
        assert completion_data['model_id'] == "test-model-0"

        # Validate rating data
        rating_data = backup_data.ratings[0]
        assert rating_data['rating'] == 6
        assert rating_data['facet_id'] == facet.id

    def test_save_and_load_round_trip(self, temp_dataset: "DatasetDatabase"):
        """
        Test saving and loading a backup file maintains data integrity.

        Flow:
        1. Create facet with test data
        2. Export to backup file
        3. Load backup from file
        4. Verify loaded data matches original

        Edge cases tested:
        - Round-trip consistency (save → load → verify)
        - File I/O with temporary files
        - Data serialization/deserialization preserves all fields
        """
        # Create test facet with sample and completion using helper
        facet = create_test_facet_with_data(temp_dataset, "Round Trip Facet", "Test round trip")

        # Create backup and save to temporary file
        with create_temp_backup_file() as temp_path:
            backup = FacetBackupFormat(temp_path)
            backup.create_backup_from_facet(temp_dataset, facet)
            saved_count = backup.save()
            assert saved_count == 1

            # Load the backup back
            loader = FacetBackupFormat(temp_path)
            loaded_count = loader.load()
            assert loaded_count == 1
            assert loader.is_loaded

            # Validate loaded data matches original
            loaded_data = loader.backup_data
            assert loaded_data is not None
            assert loaded_data.facet['name'] == "Round Trip Facet"
            assert loaded_data.facet['description'] == "Test round trip"
            assert len(loaded_data.samples) == 1
            assert len(loaded_data.completions) == 1
            assert len(loaded_data.ratings) == 1

            assert loaded_data.samples[0]['title'] == "Round Trip Facet Sample 0"
            assert loaded_data.completions[0]['completion_text'] == "round trip facet completion 0-0"
            assert loaded_data.ratings[0]['rating'] == 6

    def test_load_invalid_file_path(self):
        """Test loading from non-existent file."""
        backup = FacetBackupFormat("/non/existent/path.json")
        with pytest.raises(FileNotFoundError):
            backup.load()

    def test_load_invalid_json(self):
        """Test loading from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            temp_path = pathlib.Path(f.name)

        try:
            backup = FacetBackupFormat(temp_path)
            with pytest.raises(ValueError, match="Invalid JSON"):
                backup.load()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_missing_required_fields(self):
        """Test loading from JSON missing required fields."""
        invalid_data = {
            "pyfade_version": PYFADE_VERSION,
            # Missing format_version and other required fields
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_data, f)
            temp_path = pathlib.Path(f.name)

        try:
            backup = FacetBackupFormat(temp_path)
            with pytest.raises(ValueError, match="Missing required field"):
                backup.load()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_future_format_version(self):
        """Test loading backup with future format version."""
        future_data = {
            "pyfade_version": PYFADE_VERSION,
            "format_version": FACET_BACKUP_FORMAT_VERSION + 1,  # Future version
            "facet": {},
            "tags": [],
            "samples": [],
            "completions": [],
            "ratings": [],
            "export_timestamp": "2024-01-01T00:00:00"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(future_data, f)
            temp_path = pathlib.Path(f.name)

        try:
            backup = FacetBackupFormat(temp_path)
            with pytest.raises(ValueError, match="format version .* is newer"):
                backup.load()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_save_without_backup_data(self):
        """Test saving without creating backup data first."""
        backup = FacetBackupFormat("/tmp/test.json")
        with pytest.raises(ValueError, match="No backup data to save"):
            backup.save()

    def test_save_without_file_path(self):
        """Test saving without setting file path."""
        # Create a minimal dataset to generate backup data
        with create_temp_backup_file(suffix='.db') as temp_db_path:
            from py_fade.dataset.dataset import DatasetDatabase  # pylint: disable=import-outside-toplevel
            temp_db = DatasetDatabase(temp_db_path)
            temp_db.initialize()

            # Create minimal facet to generate backup data
            facet = Facet.create(temp_db, "Test", "Test facet")
            temp_db.commit()

            backup = FacetBackupFormat()
            backup.create_backup_from_facet(temp_db, facet)
            temp_db.dispose()

            # Now test saving without file path
            with pytest.raises(ValueError, match="No file path specified"):
                backup.save()

    def test_property_accessors(self, temp_dataset: "DatasetDatabase"):
        """Test property accessor methods."""
        facet = Facet.create(temp_dataset, "Property Test", "Test properties")
        temp_dataset.commit()

        backup = FacetBackupFormat()
        backup.create_backup_from_facet(temp_dataset, facet)

        assert backup.get_facet_name() == "Property Test"
        assert backup.get_sample_count() == 0
        assert backup.get_completion_count() == 0
        assert backup.get_rating_count() == 0

    def test_property_accessors_no_data(self):
        """Test property accessors when no data is loaded."""
        backup = FacetBackupFormat()
        assert backup.get_facet_name() is None
        assert backup.get_sample_count() == 0
        assert backup.get_completion_count() == 0
        assert backup.get_rating_count() == 0

    def test_create_backup_no_session(self, temp_dataset: "DatasetDatabase"):
        """Test creating backup when dataset session is not initialized."""
        facet = Facet.create(temp_dataset, "No Session Test", "Test no session")
        temp_dataset.commit()

        # Store the facet data before disposing the session
        facet_id = facet.id
        facet_name = facet.name

        # Close the session to simulate uninitialized state
        temp_dataset.dispose()

        # Create a new facet object with same data but without session
        detached_facet = Facet()
        detached_facet.id = facet_id
        detached_facet.name = facet_name

        backup = FacetBackupFormat()
        with pytest.raises(RuntimeError, match="Dataset session is not initialized"):
            backup.create_backup_from_facet(temp_dataset, detached_facet)


class TestFacetBackupDataClass:
    """Test the FacetBackupData dataclass."""

    def test_dataclass_creation(self):
        """Test creating FacetBackupData instance."""
        data = FacetBackupData(pyfade_version=PYFADE_VERSION, format_version=FACET_BACKUP_FORMAT_VERSION, facet={
            "id": 1,
            "name": "test"
        }, tags=[], samples=[], completions=[], ratings=[], export_timestamp="2024-01-01T00:00:00")

        assert data.pyfade_version == PYFADE_VERSION
        assert data.format_version == FACET_BACKUP_FORMAT_VERSION
        assert data.facet["name"] == "test"
        assert len(data.tags) == 0
        assert len(data.samples) == 0
        assert len(data.completions) == 0
        assert len(data.ratings) == 0
        assert data.export_timestamp == "2024-01-01T00:00:00"
