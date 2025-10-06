"""
Test suite for PromptRevision model operations.

Tests core functionality of prompt revisions including:
- Hash generation from prompt text
- Creation of new prompt revisions
- Get-or-create pattern for deduplication
- One-liner display text formatting

Edge cases covered:
- Duplicate prompt text with same parameters
- Prompt text with trailing whitespace
- Long prompt text truncation
- Prompt text with newlines and carriage returns
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from py_fade.dataset.prompt import PromptRevision
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.tag import Tag  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.completion import PromptCompletion  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.completion_rating import PromptCompletionRating  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.sample import Sample  # noqa: F401 pylint: disable=unused-import

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_hash_from_text_consistent(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that hash_from_text produces consistent hashes for same input.

    Verifies deterministic hash generation for prompt deduplication.
    """
    text = "Write a Python function to calculate factorial"
    hash1 = PromptRevision.hash_from_text(text)
    hash2 = PromptRevision.hash_from_text(text)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64-character hex string


def test_hash_from_text_different_for_different_inputs(temp_dataset: "DatasetDatabase") -> None:
    """
    Test that different prompt texts produce different hashes.

    Verifies that hash collision is avoided for different prompts.
    """
    hash1 = PromptRevision.hash_from_text("Prompt A")
    hash2 = PromptRevision.hash_from_text("Prompt B")

    assert hash1 != hash2


def test_new_from_text_creates_revision(temp_dataset: "DatasetDatabase") -> None:
    """
    Test creating a new PromptRevision from text.

    Verifies that new_from_text properly initializes all fields including
    computed hash and timestamp.
    """
    prompt_text = "Explain quantum computing"
    revision = PromptRevision.new_from_text(prompt_text, context_length=2048, max_tokens=256)

    assert revision.prompt_text == prompt_text
    assert revision.context_length == 2048
    assert revision.max_tokens == 256
    assert revision.sha256 == PromptRevision.hash_from_text(prompt_text)
    assert revision.date_created is not None


def test_get_or_create_returns_existing(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_or_create returns existing revision for duplicate prompt text.

    Verifies deduplication logic prevents duplicate prompt revisions.
    Edge case: same prompt text should always return the same revision instance.
    """
    prompt_text = "Calculate the area of a circle"
    revision1 = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length=1024, max_tokens=128)
    revision2 = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length=1024, max_tokens=128)

    assert revision1.id == revision2.id
    assert revision1.sha256 == revision2.sha256


def test_get_or_create_strips_whitespace(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_or_create handles trailing/leading whitespace correctly.

    Verifies that prompts with only whitespace differences are treated as duplicates.
    Edge case: "  text  " should match "text" after normalization.
    """
    revision1 = PromptRevision.get_or_create(temp_dataset, "  Sample prompt  ", context_length=1024, max_tokens=128)
    revision2 = PromptRevision.get_or_create(temp_dataset, "Sample prompt", context_length=1024, max_tokens=128)

    assert revision1.id == revision2.id


def test_get_by_hash_finds_existing(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_hash retrieves existing revision by prompt text.

    Verifies hash-based lookup works correctly for existing prompts.
    """
    prompt_text = "Generate a haiku about technology"
    created = PromptRevision.get_or_create(temp_dataset, prompt_text, context_length=512, max_tokens=64)
    found = PromptRevision.get_by_hash(temp_dataset, prompt_text)

    assert found is not None
    assert found.id == created.id
    assert found.prompt_text == prompt_text


def test_get_by_hash_returns_none_for_nonexistent(temp_dataset: "DatasetDatabase") -> None:
    """
    Test get_by_hash returns None for non-existent prompt.

    Verifies behavior when searching for prompt that doesn't exist in database.
    """
    found = PromptRevision.get_by_hash(temp_dataset, "This prompt does not exist")

    assert found is None


def test_prompt_text_oneliner_short_text(temp_dataset: "DatasetDatabase") -> None:
    """
    Test oneliner property for short prompt text.

    Verifies that short prompts are returned as-is, with whitespace normalized.
    Edge case: prompt shorter than max length should not be truncated.
    """
    revision = PromptRevision.new_from_text("Short prompt", context_length=1024, max_tokens=128)

    assert revision.prompt_text_oneliner == "Short prompt"


def test_prompt_text_oneliner_long_text(temp_dataset: "DatasetDatabase") -> None:
    """
    Test oneliner property truncates long prompt text.

    Verifies that long prompts are truncated with ellipsis.
    Edge case: prompt longer than 50 chars should be truncated to 47 + "...".
    """
    long_text = "This is a very long prompt text that should be truncated for display purposes in the UI"
    revision = PromptRevision.new_from_text(long_text, context_length=2048, max_tokens=256)

    oneliner = revision.prompt_text_oneliner
    assert len(oneliner) == 50
    assert oneliner.endswith("...")


def test_prompt_text_oneliner_replaces_newlines(temp_dataset: "DatasetDatabase") -> None:
    """
    Test oneliner property replaces newlines with spaces.

    Verifies that multi-line prompts are normalized to single line for display.
    Edge case: newlines and carriage returns should be replaced with spaces.
    """
    multiline_text = "Line 1\nLine 2\rLine 3"
    revision = PromptRevision.new_from_text(multiline_text, context_length=1024, max_tokens=128)

    oneliner = revision.prompt_text_oneliner
    assert "\n" not in oneliner
    assert "\r" not in oneliner
    assert oneliner == "Line 1 Line 2 Line 3"
