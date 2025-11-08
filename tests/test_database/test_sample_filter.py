"""
Tests for SampleFilter database model.

Tests for creating, retrieving, updating, and deleting complex sample filters,
as well as managing filter rules.
"""

import pytest

from py_fade.dataset.sample_filter import SampleFilter


class TestSampleFilterBasics:
    """Test basic CRUD operations for SampleFilter."""

    def test_create_sample_filter(self, temp_dataset):
        """
        Test creating a new sample filter.
        """
        sample_filter = SampleFilter.create(temp_dataset, "My Filter", "Test description")

        assert sample_filter is not None
        assert sample_filter.id is not None
        assert sample_filter.name == "My Filter"
        assert sample_filter.description == "Test description"
        assert sample_filter.filter_rules == "[]"
        assert sample_filter.date_created is not None

    def test_create_with_rules(self, temp_dataset):
        """
        Test creating a sample filter with initial rules.
        """
        rules = [{"type": "string", "value": "test", "negated": False}]
        sample_filter = SampleFilter.create(temp_dataset, "Filter with Rules", "Has rules", filter_rules=rules)

        assert sample_filter is not None
        assert sample_filter.get_rules() == rules

    def test_unique_name_enforced(self, temp_dataset):
        """
        Test that filter names must be unique.
        """
        SampleFilter.create(temp_dataset, "Unique", "First")

        with pytest.raises(ValueError, match="already exists"):
            SampleFilter.create(temp_dataset, "Unique", "Second")

    def test_empty_name_rejected(self, temp_dataset):
        """
        Test that empty filter names are rejected.
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            SampleFilter.create(temp_dataset, "", "Description")

        with pytest.raises(ValueError, match="cannot be empty"):
            SampleFilter.create(temp_dataset, "   ", "Description")


class TestSampleFilterRetrieval:
    """Test retrieving sample filters from the database."""

    def test_get_by_name(self, temp_dataset):
        """
        Test retrieving a filter by name.
        """
        SampleFilter.create(temp_dataset, "FindMe", "Test")
        found = SampleFilter.get_by_name(temp_dataset, "FindMe")

        assert found is not None
        assert found.name == "FindMe"

    def test_get_by_name_not_found(self, temp_dataset):
        """
        Test that get_by_name returns None for non-existent filters.
        """
        found = SampleFilter.get_by_name(temp_dataset, "DoesNotExist")
        assert found is None

    def test_get_by_id(self, temp_dataset):
        """
        Test retrieving a filter by ID.
        """
        created = SampleFilter.create(temp_dataset, "TestFilter", "Test")
        found = SampleFilter.get_by_id(temp_dataset, created.id)

        assert found is not None
        assert found.id == created.id
        assert found.name == "TestFilter"

    def test_get_by_id_not_found(self, temp_dataset):
        """
        Test that get_by_id returns None for non-existent filters.
        """
        found = SampleFilter.get_by_id(temp_dataset, 99999)
        assert found is None

    def test_get_all_empty(self, temp_dataset):
        """
        Test get_all with no filters in database.
        """
        filters = SampleFilter.get_all(temp_dataset)
        assert not filters

    def test_get_all_ordered_by_date(self, temp_dataset):
        """
        Test that get_all returns filters ordered by creation date (newest first).
        """
        filter1 = SampleFilter.create(temp_dataset, "First", "First filter")
        filter2 = SampleFilter.create(temp_dataset, "Second", "Second filter")
        filter3 = SampleFilter.create(temp_dataset, "Third", "Third filter")

        filters = SampleFilter.get_all(temp_dataset, order_by_date=True)

        assert len(filters) == 3
        # Newest first
        assert filters[0].id == filter3.id
        assert filters[1].id == filter2.id
        assert filters[2].id == filter1.id


class TestSampleFilterUpdate:
    """Test updating sample filter properties."""

    def test_update_name(self, temp_dataset):
        """
        Test updating a filter's name.
        """
        sample_filter = SampleFilter.create(temp_dataset, "OldName", "Description")
        sample_filter.update(temp_dataset, name="NewName")

        assert sample_filter.name == "NewName"

        # Verify persistence
        found = SampleFilter.get_by_id(temp_dataset, sample_filter.id)
        assert found.name == "NewName"

    def test_update_description(self, temp_dataset):
        """
        Test updating a filter's description.
        """
        sample_filter = SampleFilter.create(temp_dataset, "Filter", "Old description")
        sample_filter.update(temp_dataset, description="New description")

        assert sample_filter.description == "New description"

    def test_update_rules(self, temp_dataset):
        """
        Test updating filter rules.
        """
        sample_filter = SampleFilter.create(temp_dataset, "Filter", "Test")
        new_rules = [{"type": "tag", "value": 1, "negated": True}]
        sample_filter.update(temp_dataset, filter_rules=new_rules)

        assert sample_filter.get_rules() == new_rules

    def test_update_name_uniqueness_enforced(self, temp_dataset):
        """
        Test that name uniqueness is enforced during updates.
        """
        SampleFilter.create(temp_dataset, "First", "First filter")
        filter2 = SampleFilter.create(temp_dataset, "Second", "Second filter")

        with pytest.raises(ValueError, match="already exists"):
            filter2.update(temp_dataset, name="First")

    def test_update_with_empty_name_rejected(self, temp_dataset):
        """
        Test that empty names are rejected during updates.
        """
        sample_filter = SampleFilter.create(temp_dataset, "ValidName", "Description")

        with pytest.raises(ValueError, match="cannot be empty"):
            sample_filter.update(temp_dataset, name="")


class TestSampleFilterDelete:
    """Test deleting sample filters."""

    def test_delete_filter(self, temp_dataset):
        """
        Test deleting a filter.
        """
        sample_filter = SampleFilter.create(temp_dataset, "ToDelete", "Will be deleted")
        filter_id = sample_filter.id

        sample_filter.delete(temp_dataset)

        # Verify it's gone
        found = SampleFilter.get_by_id(temp_dataset, filter_id)
        assert found is None


class TestSampleFilterRulesManagement:
    """Test managing filter rules."""

    def test_get_rules_empty(self, temp_dataset):
        """
        Test getting rules from a filter with no rules.
        """
        sample_filter = SampleFilter.create(temp_dataset, "Empty", "No rules")
        rules = sample_filter.get_rules()

        assert rules == []

    def test_get_rules_with_data(self, temp_dataset):
        """
        Test getting rules from a filter with rules.
        """
        rules = [
            {
                "type": "string",
                "value": "test",
                "negated": False
            },
            {
                "type": "tag",
                "value": 1,
                "negated": True
            },
        ]
        sample_filter = SampleFilter.create(temp_dataset, "WithRules", "Has rules", filter_rules=rules)

        retrieved_rules = sample_filter.get_rules()
        assert retrieved_rules == rules

    def test_set_rules(self, temp_dataset):
        """
        Test setting rules on a filter.
        """
        sample_filter = SampleFilter.create(temp_dataset, "Filter", "Test")
        new_rules = [{"type": "facet", "value": 2, "negated": False}]

        sample_filter.set_rules(new_rules)
        temp_dataset.commit()

        # Verify persistence
        found = SampleFilter.get_by_id(temp_dataset, sample_filter.id)
        assert found.get_rules() == new_rules

    def test_get_rules_handles_invalid_json(self, temp_dataset):
        """
        Test that get_rules handles invalid JSON gracefully.
        """
        sample_filter = SampleFilter.create(temp_dataset, "BadJSON", "Invalid")

        # Manually corrupt the JSON
        session = temp_dataset.get_session()
        sample_filter.filter_rules = "not valid json {["
        session.commit()

        # Should return empty list instead of raising
        rules = sample_filter.get_rules()
        assert rules == []
