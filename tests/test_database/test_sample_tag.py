"""
Test suite for SampleTag association model operations.

Tests core functionality of sample-tag associations including:
- Creating associations between samples and tags
- Preventing duplicate associations
- Deleting associations
- Sample tag management methods (add_tag, remove_tag, has_tag, get_tags)
- Tag sample management methods (get_samples, update_sample_count)

Edge cases covered:
- Duplicate sample-tag associations
- Removing non-existent associations
- Multiple tags per sample
- Multiple samples per tag
- Sample count updates
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.sample import Sample
from py_fade.dataset.sample_tag import SampleTag
from py_fade.dataset.tag import Tag
from py_fade.dataset.prompt import PromptRevision
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.completion import PromptCompletion  # noqa: F401 pylint: disable=unused-import
from tests.helpers.data_helpers import create_samples_with_tag

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_create_sample_tag_association(temp_dataset: "DatasetDatabase") -> None:
    """
    Test creating a sample-tag association.

    Verifies that associations can be created between samples and tags.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Create association
    sample_tag = SampleTag.create(temp_dataset, sample, tag)
    temp_dataset.commit()

    assert sample_tag.id is not None
    assert sample_tag.sample_id == sample.id
    assert sample_tag.tag_id == tag.id
    assert sample_tag.date_created is not None


def test_create_duplicate_association_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating a duplicate sample-tag association raises ValueError.

    Edge case: attempting to tag a sample with the same tag twice should fail.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Create first association
    SampleTag.create(temp_dataset, sample, tag)
    temp_dataset.commit()

    # Attempt to create duplicate association
    with pytest.raises(ValueError, match="already tagged"):
        SampleTag.create(temp_dataset, sample, tag)


def test_delete_sample_tag_association(temp_dataset: "DatasetDatabase") -> None:
    """
    Test deleting a sample-tag association.

    Verifies that associations can be deleted.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Create association
    SampleTag.create(temp_dataset, sample, tag)
    temp_dataset.commit()

    # Verify association exists
    session = temp_dataset.get_session()
    existing = session.query(SampleTag).filter_by(sample_id=sample.id, tag_id=tag.id).first()
    assert existing is not None

    # Delete association
    SampleTag.delete_association(temp_dataset, sample, tag)
    temp_dataset.commit()

    # Verify association is deleted
    deleted = session.query(SampleTag).filter_by(sample_id=sample.id, tag_id=tag.id).first()
    assert deleted is None


def test_delete_non_existent_association_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that deleting a non-existent association raises ValueError.

    Edge case: attempting to remove a tag from a sample that doesn't have it should fail.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Attempt to delete non-existent association
    with pytest.raises(ValueError, match="not tagged"):
        SampleTag.delete_association(temp_dataset, sample, tag)


def test_sample_add_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test adding a tag to a sample using Sample.add_tag method.

    Verifies that tags can be added to samples through the Sample model.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Add tag to sample
    sample.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Verify association exists
    assert sample.has_tag(temp_dataset, tag)


def test_sample_remove_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test removing a tag from a sample using Sample.remove_tag method.

    Verifies that tags can be removed from samples through the Sample model.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Add tag to sample
    sample.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Remove tag from sample
    sample.remove_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Verify association is deleted
    assert not sample.has_tag(temp_dataset, tag)


def test_sample_get_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test retrieving all tags for a sample using Sample.get_tags method.

    Verifies that all tags associated with a sample can be retrieved.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create multiple tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples")
    tag3 = Tag.create(temp_dataset, "Complete", "Complete samples")
    temp_dataset.commit()

    # Add tags to sample
    sample.add_tag(temp_dataset, tag1)
    sample.add_tag(temp_dataset, tag2)
    sample.add_tag(temp_dataset, tag3)
    temp_dataset.commit()

    # Get all tags for sample
    tags = sample.get_tags(temp_dataset)

    # Verify all tags are returned (ordered by name)
    assert len(tags) == 3
    tag_names = [tag.name for tag in tags]
    assert tag_names == ["Complete", "Important", "Reviewed"]  # Alphabetically sorted


def test_sample_get_tags_empty(temp_dataset: "DatasetDatabase") -> None:
    """
    Test retrieving tags for a sample with no tags.

    Edge case: sample without any tags should return empty list.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Get tags for sample (should be empty)
    tags = sample.get_tags(temp_dataset)

    assert len(tags) == 0


def test_sample_has_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test checking if a sample has a specific tag.

    Verifies that has_tag returns True for associated tags and False otherwise.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples")
    temp_dataset.commit()

    # Add only tag1 to sample
    sample.add_tag(temp_dataset, tag1)
    temp_dataset.commit()

    # Verify has_tag works correctly
    assert sample.has_tag(temp_dataset, tag1) is True
    assert sample.has_tag(temp_dataset, tag2) is False


def test_tag_get_samples(temp_dataset: "DatasetDatabase") -> None:
    """
    Test retrieving all samples for a tag using Tag.get_samples method.

    Verifies that all samples associated with a tag can be retrieved.
    """
    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Create samples and add them to the tag
    samples_list = create_samples_with_tag(temp_dataset, tag)
    assert len(samples_list) == 3
    sample1, sample2, sample3 = samples_list[0], samples_list[1], samples_list[2]

    # Get all samples for tag
    samples = tag.get_samples(temp_dataset)

    # Verify all samples are returned (ordered by date created, newest first)
    assert len(samples) == 3
    sample_ids = [sample.id for sample in samples]
    # Samples should be ordered by date_created descending (newest first)
    # So sample3, sample2, sample1
    assert sample_ids == [sample3.id, sample2.id, sample1.id]


def test_tag_get_samples_empty(temp_dataset: "DatasetDatabase") -> None:
    """
    Test retrieving samples for a tag with no samples.

    Edge case: tag without any samples should return empty list.
    """
    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Get samples for tag (should be empty)
    samples = tag.get_samples(temp_dataset)

    assert len(samples) == 0


def test_tag_update_sample_count(temp_dataset: "DatasetDatabase") -> None:
    """
    Test updating the sample count for a tag.

    Verifies that total_samples is correctly updated based on associations.
    """
    # Create multiple samples
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample1 = Sample.create_if_unique(temp_dataset, "Sample 1", prompt_revision)
    temp_dataset.commit()

    prompt_revision2 = PromptRevision.get_or_create(temp_dataset, "Test prompt 2", 2048, 512)
    sample2 = Sample.create_if_unique(temp_dataset, "Sample 2", prompt_revision2)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Initially, total_samples should be 0
    assert tag.total_samples == 0

    # Add tag to samples
    sample1.add_tag(temp_dataset, tag)
    sample2.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Update sample count
    tag.update_sample_count(temp_dataset)
    temp_dataset.commit()

    # Verify count is correct
    assert tag.total_samples == 2

    # Remove one tag association
    sample1.remove_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Update sample count again
    tag.update_sample_count(temp_dataset)
    temp_dataset.commit()

    # Verify count is updated
    assert tag.total_samples == 1


def test_multiple_tags_per_sample(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that a sample can have multiple tags.

    Verifies many-to-many relationship allows multiple tags per sample.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create multiple tags
    tag1 = Tag.create(temp_dataset, "Important", "Important samples")
    tag2 = Tag.create(temp_dataset, "Reviewed", "Reviewed samples")
    tag3 = Tag.create(temp_dataset, "Complete", "Complete samples")
    temp_dataset.commit()

    # Add all tags to sample
    sample.add_tag(temp_dataset, tag1)
    sample.add_tag(temp_dataset, tag2)
    sample.add_tag(temp_dataset, tag3)
    temp_dataset.commit()

    # Verify all tags are associated
    tags = sample.get_tags(temp_dataset)
    assert len(tags) == 3


def test_multiple_samples_per_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that a tag can be associated with multiple samples.

    Verifies many-to-many relationship allows multiple samples per tag.
    """
    # Create multiple samples
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample1 = Sample.create_if_unique(temp_dataset, "Sample 1", prompt_revision)
    temp_dataset.commit()

    prompt_revision2 = PromptRevision.get_or_create(temp_dataset, "Test prompt 2", 2048, 512)
    sample2 = Sample.create_if_unique(temp_dataset, "Sample 2", prompt_revision2)
    temp_dataset.commit()

    prompt_revision3 = PromptRevision.get_or_create(temp_dataset, "Test prompt 3", 2048, 512)
    sample3 = Sample.create_if_unique(temp_dataset, "Sample 3", prompt_revision3)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Add tag to all samples
    sample1.add_tag(temp_dataset, tag)
    sample2.add_tag(temp_dataset, tag)
    sample3.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    # Verify all samples are associated
    samples = tag.get_samples(temp_dataset)
    assert len(samples) == 3


def test_cascade_delete_sample_deletes_associations(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that deleting a sample cascades to delete its tag associations.

    Verifies cascade behavior for sample deletion.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Add tag to sample
    sample.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    sample_id = sample.id
    tag_id = tag.id

    # Verify association exists
    session = temp_dataset.get_session()
    assert session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag_id).first() is not None

    # Delete sample
    session.delete(sample)
    temp_dataset.commit()

    # Verify association is deleted (cascade)
    assert session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag_id).first() is None

    # Verify tag still exists
    assert Tag.get_by_id(temp_dataset, tag_id) is not None


def test_cascade_delete_tag_deletes_associations(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that deleting a tag cascades to delete its sample associations.

    Verifies cascade behavior for tag deletion.
    """
    # Create a sample
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample", prompt_revision)
    temp_dataset.commit()

    # Create a tag
    tag = Tag.create(temp_dataset, "Important", "Important samples")
    temp_dataset.commit()

    # Add tag to sample
    sample.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    sample_id = sample.id
    tag_id = tag.id

    # Verify association exists
    session = temp_dataset.get_session()
    assert session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag_id).first() is not None

    # Delete tag
    tag.delete(temp_dataset)
    temp_dataset.commit()

    # Verify association is deleted (cascade)
    assert session.query(SampleTag).filter_by(sample_id=sample_id, tag_id=tag_id).first() is None

    # Verify sample still exists
    assert session.query(Sample).filter_by(id=sample_id).first() is not None
