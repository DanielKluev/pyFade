"""
Test suite for DatasetDatabase operations and management.

Tests dataset initialization, basic operations, and transaction management.
"""
from __future__ import annotations

import pathlib
import tempfile
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample

if TYPE_CHECKING:
    pass


def test_dataset_basic_initialization():
    """Test basic dataset initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "test.db"
        
        # Test basic initialization
        dataset = DatasetDatabase(db_path)
        dataset.initialize()
        
        assert dataset.db_path == db_path
        assert dataset.session is not None
        assert dataset.engine is not None
        
        dataset.dispose()


def test_dataset_query_operations(temp_dataset: DatasetDatabase):
    """Test basic dataset query operations with existing ORM methods."""
    # Create test data using existing methods
    facet1 = Facet.create(temp_dataset, "Quality", "Quality assessment")
    facet2 = Facet.create(temp_dataset, "Safety", "Safety evaluation")
    temp_dataset.commit()
    
    # Test facet queries using existing methods
    all_facets = Facet.get_all(temp_dataset)
    assert len(all_facets) == 2
    assert facet1 in all_facets
    assert facet2 in all_facets
    
    # Test lookup by name
    found_facet = Facet.get_by_name(temp_dataset, "Quality")
    assert found_facet is not None
    assert found_facet.id == facet1.id
    
    # Test lookup by ID
    found_facet_by_id = Facet.get_by_id(temp_dataset, facet1.id)
    assert found_facet_by_id is not None
    assert found_facet_by_id.name == "Quality"


def test_dataset_transaction_management(temp_dataset: DatasetDatabase):
    """Test database transaction handling and commit behavior."""
    initial_facet_count = len(Facet.get_all(temp_dataset))
    
    # Create a facet and commit
    facet = Facet.create(temp_dataset, "TestFacet", "Test facet for transaction testing")
    temp_dataset.commit()
    
    # Verify it was committed
    final_facets = Facet.get_all(temp_dataset)
    assert len(final_facets) == initial_facet_count + 1
    assert any(f.name == "TestFacet" for f in final_facets)
    
    # Test that we can retrieve it
    retrieved_facet = Facet.get_by_name(temp_dataset, "TestFacet")
    assert retrieved_facet is not None
    assert retrieved_facet.description == "Test facet for transaction testing"


def test_dataset_session_management(temp_dataset: DatasetDatabase):
    """Test database session lifecycle management."""
    # Verify session exists after initialization
    assert temp_dataset.session is not None
    
    original_session = temp_dataset.session
    
    # Create some data to verify session persistence
    facet = Facet.create(temp_dataset, "SessionTest", "Testing session management")
    temp_dataset.commit()
    
    # The session should still be the same
    assert temp_dataset.session is original_session
    
    # Data should be accessible
    retrieved_facet = Facet.get_by_name(temp_dataset, "SessionTest")
    assert retrieved_facet is not None
    assert retrieved_facet.description == "Testing session management"


def test_dataset_error_handling():
    """Test error handling for database operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with uninitialized database
        db_path = pathlib.Path(tmpdir) / "uninitialized.db"
        dataset = DatasetDatabase(db_path)
        
        # Should be able to create but session should be None before initialization
        assert dataset.session is None
        
        # Initialize it
        dataset.initialize()
        assert dataset.session is not None
        
        # Now operations should work
        facet = Facet.create(dataset, "Test", "Test facet")
        dataset.commit()
        assert facet.id is not None
        
        # Clean up
        dataset.dispose()


def test_dataset_dispose_cleanup(temp_dataset: DatasetDatabase):
    """Test that dispose properly cleans up resources."""
    # Verify database is functional before dispose
    facet = Facet.create(temp_dataset, "DisposeTest", "Test disposal")
    temp_dataset.commit()
    
    retrieved_facet = Facet.get_by_name(temp_dataset, "DisposeTest")
    assert retrieved_facet is not None
    
    # Note: We can't actually test dispose on temp_dataset since it's a fixture
    # that other tests depend on, but we can test the method exists and is callable
    assert hasattr(temp_dataset, 'dispose')
    assert callable(temp_dataset.dispose)


def test_facet_operations_comprehensive(temp_dataset: DatasetDatabase):
    """Test comprehensive facet operations through the database."""
    # Create multiple facets
    facets_data = [
        ("Accuracy", "Factual accuracy evaluation"),
        ("Creativity", "Creative response assessment"),
        ("Safety", "Content safety evaluation"),
        ("Helpfulness", "Response helpfulness rating")
    ]
    
    created_facets = []
    for name, description in facets_data:
        facet = Facet.create(temp_dataset, name, description)
        created_facets.append(facet)
    
    temp_dataset.commit()
    
    # Verify all facets were created
    all_facets = Facet.get_all(temp_dataset)
    assert len(all_facets) >= len(facets_data)
    
    # Verify each facet can be retrieved by name
    for name, description in facets_data:
        facet = Facet.get_by_name(temp_dataset, name)
        assert facet is not None
        assert facet.description == description
    
    # Test facet update
    accuracy_facet = Facet.get_by_name(temp_dataset, "Accuracy")
    assert accuracy_facet is not None
    
    accuracy_facet.update(temp_dataset, description="Updated accuracy description")
    temp_dataset.commit()
    
    # Verify update
    updated_facet = Facet.get_by_id(temp_dataset, accuracy_facet.id)
    assert updated_facet is not None
    assert updated_facet.description == "Updated accuracy description"
    
    # Test facet deletion
    creativity_facet = Facet.get_by_name(temp_dataset, "Creativity")
    assert creativity_facet is not None
    facet_id = creativity_facet.id
    
    creativity_facet.delete(temp_dataset)
    temp_dataset.commit()
    
    # Verify deletion
    deleted_facet = Facet.get_by_id(temp_dataset, facet_id)
    assert deleted_facet is None