"""
Test suite for CompletionTag association model operations.

Tests core functionality of completion-tag associations including:
- Creating associations between completions and tags
- Preventing duplicate associations
- Deleting associations
- Completion tag management methods (add_tag, remove_tag, has_tag, get_tags, is_wip)

Edge cases covered:
- Duplicate completion-tag associations
- Removing non-existent associations
- Multiple tags per completion
- WIP tag detection and is_wip() method
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion, WIP_TAG_NAME
from py_fade.dataset.completion_tag import CompletionTag
from py_fade.dataset.tag import Tag
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def _create_completion(temp_dataset: "DatasetDatabase") -> PromptCompletion:
    """
    Create a saved PromptCompletion for testing.

    Returns a persisted completion associated with a prompt and sample.
    """
    prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt for completion tag", 2048, 512)
    sample = Sample.create_if_unique(temp_dataset, "Test Sample CT", prompt_revision)
    if sample is None:
        sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
        temp_dataset.session.add(sample)  # type: ignore[union-attr]
    completion_text = "Test completion for tag testing"
    completion = PromptCompletion(
        prompt_revision_id=prompt_revision.id,
        sha256=hashlib.sha256(completion_text.encode()).hexdigest(),
        model_id="test-model",
        temperature=0.7,
        top_k=40,
        completion_text=completion_text,
        context_length=2048,
        max_tokens=512,
        is_truncated=False,
    )
    temp_dataset.session.add(completion)  # type: ignore[union-attr]
    temp_dataset.commit()
    return completion


def test_create_completion_tag_association(temp_dataset: "DatasetDatabase") -> None:
    """
    Test creating a completion-tag association.

    Verifies that associations can be created between completions and tags.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "WIP Tag", "Work in progress", scope="completions")
    temp_dataset.commit()

    completion_tag = CompletionTag.create(temp_dataset, completion, tag)
    temp_dataset.commit()

    assert completion_tag.id is not None
    assert completion_tag.completion_id == completion.id
    assert completion_tag.tag_id == tag.id
    assert completion_tag.date_created is not None


def test_create_duplicate_completion_tag_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that creating a duplicate completion-tag association raises ValueError.

    Verifies that duplicate associations are rejected with an appropriate error.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "WIP Tag", "Work in progress", scope="completions")
    temp_dataset.commit()

    CompletionTag.create(temp_dataset, completion, tag)
    temp_dataset.commit()

    with pytest.raises(ValueError, match="already tagged"):
        CompletionTag.create(temp_dataset, completion, tag)


def test_delete_completion_tag_association(temp_dataset: "DatasetDatabase") -> None:
    """
    Test deleting a completion-tag association.

    Verifies that associations can be removed between completions and tags.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "WIP Tag", "Work in progress", scope="completions")
    temp_dataset.commit()

    CompletionTag.create(temp_dataset, completion, tag)
    temp_dataset.commit()

    # Verify association exists
    assert completion.has_tag(temp_dataset, tag)

    # Delete association
    CompletionTag.delete_association(temp_dataset, completion, tag)
    temp_dataset.commit()

    # Verify association no longer exists
    assert not completion.has_tag(temp_dataset, tag)


def test_delete_nonexistent_completion_tag_raises_error(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that deleting a non-existent completion-tag association raises ValueError.

    Verifies that attempting to remove an association that does not exist raises an error.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "WIP Tag", "Work in progress", scope="completions")
    temp_dataset.commit()

    with pytest.raises(ValueError, match="not tagged"):
        CompletionTag.delete_association(temp_dataset, completion, tag)


def test_completion_add_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test add_tag method on PromptCompletion.

    Verifies that tags can be added to a completion via the add_tag method.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "Test Tag", "Test description", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    assert completion.has_tag(temp_dataset, tag)


def test_completion_remove_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test remove_tag method on PromptCompletion.

    Verifies that tags can be removed from a completion via the remove_tag method.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "Test Tag", "Test description", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    assert completion.has_tag(temp_dataset, tag)

    completion.remove_tag(temp_dataset, tag)
    temp_dataset.commit()

    assert not completion.has_tag(temp_dataset, tag)


def test_completion_has_tag_returns_false_when_no_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test has_tag returns False when no tag is assigned.

    Verifies that has_tag correctly returns False for unassigned tags.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "Test Tag", "Test description", scope="completions")
    temp_dataset.commit()

    assert not completion.has_tag(temp_dataset, tag)


def test_completion_get_tags_returns_all_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_tags returns all assigned tags.

    Verifies that get_tags returns all tags associated with the completion.
    """
    completion = _create_completion(temp_dataset)
    tag1 = Tag.create(temp_dataset, "Tag One", "First tag", scope="completions")
    tag2 = Tag.create(temp_dataset, "Tag Two", "Second tag", scope="both")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, tag1)
    completion.add_tag(temp_dataset, tag2)
    temp_dataset.commit()

    tags = completion.get_tags(temp_dataset)
    tag_names = {tag.name for tag in tags}
    assert "Tag One" in tag_names
    assert "Tag Two" in tag_names
    assert len(tags) == 2


def test_completion_get_tags_empty_when_no_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_tags returns empty list when no tags are assigned.

    Verifies that get_tags correctly returns an empty list for untagged completions.
    """
    completion = _create_completion(temp_dataset)
    temp_dataset.commit()

    assert not completion.get_tags(temp_dataset)


def test_completion_is_wip_returns_true_for_wip_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test is_wip returns True when Completion::WIP tag is assigned.

    Verifies that is_wip correctly identifies WIP completions.
    """
    completion = _create_completion(temp_dataset)
    wip_tag = Tag.create(temp_dataset, WIP_TAG_NAME, "Work in progress completion", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, wip_tag)
    temp_dataset.commit()

    assert completion.is_wip(temp_dataset)


def test_completion_is_wip_returns_false_without_wip_tag(temp_dataset: "DatasetDatabase") -> None:
    """
    Test is_wip returns False when Completion::WIP tag is not assigned.

    Verifies that is_wip correctly returns False for non-WIP completions.
    """
    completion = _create_completion(temp_dataset)
    other_tag = Tag.create(temp_dataset, "Completion::Other", "Another completion tag", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, other_tag)
    temp_dataset.commit()

    assert not completion.is_wip(temp_dataset)


def test_completion_is_wip_returns_false_without_any_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test is_wip returns False when no tags are assigned.

    Verifies that is_wip correctly returns False for completions with no tags.
    """
    completion = _create_completion(temp_dataset)
    temp_dataset.commit()

    assert not completion.is_wip(temp_dataset)


def test_wip_tag_name_constant() -> None:
    """
    Test that WIP_TAG_NAME constant has the expected value.

    Verifies the constant used to identify WIP completions.
    """
    assert WIP_TAG_NAME == "Completion::WIP"


def test_completion_multiple_tags_independent(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that multiple tags on a completion are managed independently.

    Verifies that adding/removing one tag does not affect other tags on the same completion.
    """
    completion = _create_completion(temp_dataset)
    tag1 = Tag.create(temp_dataset, "Tag A", "First tag", scope="completions")
    tag2 = Tag.create(temp_dataset, WIP_TAG_NAME, "WIP tag", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, tag1)
    completion.add_tag(temp_dataset, tag2)
    temp_dataset.commit()

    # Both tags present
    assert completion.has_tag(temp_dataset, tag1)
    assert completion.is_wip(temp_dataset)

    # Remove tag1, WIP should remain
    completion.remove_tag(temp_dataset, tag1)
    temp_dataset.commit()

    assert not completion.has_tag(temp_dataset, tag1)
    assert completion.is_wip(temp_dataset)


def test_tag_delete_cascades_to_completion_tags(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that deleting a tag cascades to remove associated completion_tags entries.

    Verifies referential integrity when tags are deleted.
    """
    completion = _create_completion(temp_dataset)
    tag = Tag.create(temp_dataset, "To Delete", "Tag to be deleted", scope="completions")
    temp_dataset.commit()

    completion.add_tag(temp_dataset, tag)
    temp_dataset.commit()

    assert completion.has_tag(temp_dataset, tag)

    # Delete the tag - should cascade to completion_tags
    tag.delete(temp_dataset)
    temp_dataset.commit()

    # Verify the tag no longer exists
    session = temp_dataset.get_session()
    assert session.query(CompletionTag).filter_by(completion_id=completion.id).count() == 0
