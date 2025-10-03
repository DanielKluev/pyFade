"""
Test Sample notes field functionality.

Tests for the notes field added to the Sample model, ensuring proper
persistence, retrieval, and UI integration.
"""
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
# Import all models to ensure proper table creation
from py_fade.dataset.facet import Facet  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.tag import Tag  # noqa: F401 pylint: disable=unused-import
from py_fade.dataset.export_template import ExportTemplate  # noqa: F401 pylint: disable=unused-import


class TestSampleNotes:
    """Tests for Sample notes field persistence and operations."""

    def test_sample_creation_with_notes(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that a sample can be created with notes field.

        Verifies that notes are properly persisted and retrieved.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for notes", context_length=2048, max_tokens=256
        )

        # Create sample with notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample with Notes",
            prompt_revision=prompt_revision,
            group_path="test/group",
            notes="These are important notes for annotators.",
        )

        assert sample is not None
        assert sample.notes == "These are important notes for annotators."
        assert sample.title == "Test Sample with Notes"
        assert sample.group_path == "test/group"

    def test_sample_creation_without_notes(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that a sample can be created without notes field (None).

        Verifies backward compatibility when notes are not provided.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt without notes", context_length=2048, max_tokens=256
        )

        # Create sample without notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample without Notes",
            prompt_revision=prompt_revision,
            group_path="test/group",
        )

        assert sample is not None
        assert sample.notes is None
        assert sample.title == "Test Sample without Notes"

    def test_sample_notes_persistence(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that notes are properly persisted to database.

        Verifies that notes survive database session commits and reloads.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for persistence", context_length=2048, max_tokens=256
        )

        # Create sample with notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Persistence",
            prompt_revision=prompt_revision,
            notes="Notes that should persist.",
        )

        assert sample is not None
        sample_id = sample.id
        temp_dataset.session.commit()

        # Reload sample from database
        reloaded_sample = temp_dataset.session.query(Sample).filter_by(id=sample_id).first()
        assert reloaded_sample is not None
        assert reloaded_sample.notes == "Notes that should persist."

    def test_sample_notes_update(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that notes can be updated after sample creation.

        Verifies that notes field can be modified and persisted.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for update", context_length=2048, max_tokens=256
        )

        # Create sample with initial notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Update",
            prompt_revision=prompt_revision,
            notes="Initial notes.",
        )

        assert sample is not None
        sample_id = sample.id

        # Update notes
        sample.notes = "Updated notes with more information."
        temp_dataset.session.commit()

        # Reload and verify update
        reloaded_sample = temp_dataset.session.query(Sample).filter_by(id=sample_id).first()
        assert reloaded_sample is not None
        assert reloaded_sample.notes == "Updated notes with more information."

    def test_sample_notes_empty_string_vs_none(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test distinction between empty string and None for notes.

        Verifies that empty strings are handled correctly (should be stored as None).
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for empty", context_length=2048, max_tokens=256
        )

        # Create sample with empty string notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Empty Notes",
            prompt_revision=prompt_revision,
            notes="",
        )

        assert sample is not None
        # Empty string should be stored as-is by the database
        # The widget will convert empty strings to None when saving
        assert sample.notes == ""

    def test_sample_notes_multiline(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that multiline notes are properly stored.

        Verifies that notes with newlines are preserved.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for multiline", context_length=2048, max_tokens=256
        )

        multiline_notes = "Line 1: Important note\nLine 2: Another note\nLine 3: Final note"

        # Create sample with multiline notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Multiline",
            prompt_revision=prompt_revision,
            notes=multiline_notes,
        )

        assert sample is not None
        assert sample.notes == multiline_notes
        assert "\n" in sample.notes

    def test_sample_new_copy_preserves_notes(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that new_copy() method preserves notes field.

        Verifies that notes are copied when creating a copy of a sample.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for copy", context_length=2048, max_tokens=256
        )

        # Create sample with notes
        original_sample = Sample.create_if_unique(
            temp_dataset,
            title="Original Sample",
            prompt_revision=prompt_revision,
            notes="Original notes to be copied.",
        )

        assert original_sample is not None

        # Create a copy
        copied_sample = original_sample.new_copy()

        assert copied_sample.notes == "Original notes to be copied."
        assert copied_sample.title == "Original Sample (Copy)"
        assert copied_sample.group_path == original_sample.group_path
        assert copied_sample.prompt_revision == original_sample.prompt_revision

    def test_sample_notes_with_special_characters(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that notes with special characters are properly stored.

        Verifies that notes with quotes, unicode, and other special characters work correctly.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for special chars", context_length=2048, max_tokens=256
        )

        special_notes = "Notes with \"quotes\" and 'apostrophes' and unicode: 你好 🎉"

        # Create sample with special character notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Special Chars",
            prompt_revision=prompt_revision,
            notes=special_notes,
        )

        assert sample is not None
        assert sample.notes == special_notes

    def test_sample_notes_long_text(self, temp_dataset: DatasetDatabase) -> None:
        """
        Test that long notes text is properly stored.

        Verifies that notes field can handle longer text content.
        """
        # Create a prompt revision
        prompt_revision = PromptRevision.get_or_create(
            temp_dataset, "Test prompt for long text", context_length=2048, max_tokens=256
        )

        long_notes = "This is a very long note. " * 100  # Create a long string

        # Create sample with long notes
        sample = Sample.create_if_unique(
            temp_dataset,
            title="Test Sample Long Notes",
            prompt_revision=prompt_revision,
            notes=long_notes,
        )

        assert sample is not None
        assert sample.notes == long_notes
        assert len(sample.notes) > 1000
