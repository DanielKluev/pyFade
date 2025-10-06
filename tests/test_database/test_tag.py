"""
Test suite for Tag model operations.

Tests core functionality of tags including:
- Tag creation with scope validation
- Name uniqueness enforcement
- Scope normalization
- Get operations (by name, by ID, get all)
- Update and delete operations

Edge cases covered:
- Empty tag names
- Whitespace-only tag names
- Invalid scopes
- Duplicate tag names
- Case-insensitive scope normalization
- Tags with empty descriptions
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.tag import Tag
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.sample import Sample  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.prompt import PromptRevision  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.completion import PromptCompletion  # noqa: F401 pylint: disable=unused-import

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_normalize_scope_valid_scopes() -> None:
    """
    Test that normalize_scope accepts all valid scope values.

    Verifies that 'samples', 'completions', and 'both' are accepted.
    """
    assert Tag.normalize_scope("samples") == "samples"
    assert Tag.normalize_scope("completions") == "completions"
    assert Tag.normalize_scope("both") == "both"


def test_normalize_scope_case_insensitive() -> None:
    """
    Test that normalize_scope is case-insensitive.

    Edge case: 'SAMPLES', 'Samples', 'sAmPlEs' should all normalize to 'samples'.
    """
    assert Tag.normalize_scope("SAMPLES") == "samples"
    assert Tag.normalize_scope("Samples") == "samples"
    assert Tag.normalize_scope("CoMpLeTiOnS") == "completions"


def test_normalize_scope_strips_whitespace() -> None:
    """
    Test that normalize_scope strips leading/trailing whitespace.

    Edge case: '  samples  ' should normalize to 'samples'.
    """
    assert Tag.normalize_scope("  samples  ") == "samples"
    assert Tag.normalize_scope("\tboth\n") == "both"


def test_normalize_scope_none_defaults_to_both() -> None:
    """
    Test that normalize_scope treats None as 'both'.

    Edge case: None scope should default to 'both'.
    """
    assert Tag.normalize_scope(None) == "both"


def test_normalize_scope_invalid_raises_error() -> None:
    """
    Test that normalize_scope raises ValueError for invalid scopes.

    Edge case: invalid scope values should be rejected.
    """
    with pytest.raises(ValueError, match="Tag scope must be one of"):
        Tag.normalize_scope("invalid")

    with pytest.raises(ValueError, match="Tag scope must be one of"):
        Tag.normalize_scope("sample")  # Note: 'sample' not 'samples'


def test_create_tag_basic(temp_dataset: "DatasetDatabase") -> None:
    """
    Test creating a tag with valid parameters.

    Verifies that tag creation with name and description works correctly.
    """
    tag = Tag.create(temp_dataset, "Testing", "For testing purposes")
    temp_dataset.commit()

    assert tag.id is not None
    assert tag.name == "Testing"
    assert tag.description == "For testing purposes"
    assert tag.scope == "both"  # Default scope
    assert tag.total_samples == 0
    assert tag.date_created is not None


def test_create_tag_with_custom_scope(temp_dataset: "DatasetDatabase") -> None:
    """
    Test creating a tag with custom scope.

    Verifies that scope parameter is properly set during creation.
    """
    tag = Tag.create(temp_dataset, "SampleTag", "Only for samples", scope="samples")
    temp_dataset.commit()

    assert tag.scope == "samples"


def test_create_tag_empty_name_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating a tag with empty name raises ValueError.

    Edge case: empty string or whitespace-only names should be rejected.
    """
    with pytest.raises(ValueError, match="Tag name cannot be empty"):
        Tag.create(temp_dataset, "", "Description")

    with pytest.raises(ValueError, match="Tag name cannot be empty"):
        Tag.create(temp_dataset, "   ", "Description")


def test_create_tag_empty_description_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating a tag with empty description raises ValueError.

    Edge case: empty string or whitespace-only descriptions should be rejected.
    """
    with pytest.raises(ValueError, match="Tag description cannot be empty"):
        Tag.create(temp_dataset, "ValidName", "")

    with pytest.raises(ValueError, match="Tag description cannot be empty"):
        Tag.create(temp_dataset, "ValidName", "   ")


def test_create_tag_duplicate_name_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating a tag with duplicate name raises ValueError.

    Edge case: tag names must be unique within a dataset.
    """
    Tag.create(temp_dataset, "Duplicate", "First tag")
    temp_dataset.commit()

    with pytest.raises(ValueError, match="already exists"):
        Tag.create(temp_dataset, "Duplicate", "Second tag")


def test_create_tag_name_trimmed(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that tag names are trimmed of leading/trailing whitespace.

    Edge case: '  TagName  ' should be stored as 'TagName'.
    """
    tag = Tag.create(temp_dataset, "  SpacedTag  ", "Description")
    temp_dataset.commit()

    assert tag.name == "SpacedTag"


def test_get_by_name_finds_existing(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_name retrieves existing tag.

    Verifies that tags can be looked up by name.
    """
    created = Tag.create(temp_dataset, "FindMe", "Description")
    temp_dataset.commit()
    found = Tag.get_by_name(temp_dataset, "FindMe")

    assert found is not None
    assert found.id == created.id
    assert found.name == "FindMe"


def test_get_by_name_returns_none_for_nonexistent(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_name returns None for non-existent tag.

    Verifies behavior when searching for tag that doesn't exist.
    """
    found = Tag.get_by_name(temp_dataset, "DoesNotExist")

    assert found is None


def test_get_by_name_empty_string_returns_none(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_name returns None for empty string.

    Edge case: empty or whitespace-only names should return None.
    """
    assert Tag.get_by_name(temp_dataset, "") is None
    assert Tag.get_by_name(temp_dataset, "   ") is None


def test_get_by_id_finds_existing(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_id retrieves existing tag.

    Verifies that tags can be looked up by ID.
    """
    created = Tag.create(temp_dataset, "IDTest", "Description")
    temp_dataset.commit()
    found = Tag.get_by_id(temp_dataset, created.id)

    assert found is not None
    assert found.id == created.id
    assert found.name == "IDTest"


def test_get_by_id_returns_none_for_nonexistent(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_id returns None for non-existent ID.

    Verifies behavior when searching for tag with invalid ID.
    """
    found = Tag.get_by_id(temp_dataset, 99999)

    assert found is None


def test_get_all_returns_empty_list_initially(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_all returns empty list when no tags exist.

    Verifies behavior on fresh dataset with no tags.
    """
    tags = Tag.get_all(temp_dataset)

    assert not tags


def test_get_all_returns_all_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_all returns all tags in the dataset.

    Verifies that all created tags are returned by get_all.
    """
    Tag.create(temp_dataset, "Tag1", "First tag")
    Tag.create(temp_dataset, "Tag2", "Second tag")
    Tag.create(temp_dataset, "Tag3", "Third tag")
    temp_dataset.commit()

    tags = Tag.get_all(temp_dataset)

    assert len(tags) == 3
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"Tag1", "Tag2", "Tag3"}


def test_get_all_ordered_by_date_descending(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_all returns tags ordered by creation date (newest first).

    Verifies default ordering behavior.
    """
    Tag.create(temp_dataset, "Oldest", "Created first")
    Tag.create(temp_dataset, "Middle", "Created second")
    Tag.create(temp_dataset, "Newest", "Created third")
    temp_dataset.commit()

    tags = Tag.get_all(temp_dataset, order_by_date=True)

    # Newest should be first
    assert tags[0].name == "Newest"
    assert tags[2].name == "Oldest"


def test_update_tag_description(temp_dataset: "DatasetDatabase") -> None:
    """
    Test updating tag description.

    Verifies that tag attributes can be modified and persisted.
    """
    tag = Tag.create(temp_dataset, "Updateable", "Original description")
    temp_dataset.commit()
    original_id = tag.id

    tag.description = "Updated description"
    temp_dataset.commit()

    updated = Tag.get_by_id(temp_dataset, original_id)
    assert updated.description == "Updated description"


def test_delete_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test deleting a tag.

    Verifies that tags can be deleted from the database.
    """
    tag = Tag.create(temp_dataset, "ToDelete", "Will be deleted")
    temp_dataset.commit()
    tag_id = tag.id

    temp_dataset.session.delete(tag)
    temp_dataset.commit()

    deleted = Tag.get_by_id(temp_dataset, tag_id)
    assert deleted is None
