"""
Tests for archiving completions and cleaning alternative logprobs.

This test module validates:
- Alternative logprobs are cleaned when archiving a completion
- Sampled logprobs are preserved when archiving
- Archived completions are not loaded into generation cache
- Unarchiving does not restore alternative logprobs
"""
import hashlib

from py_fade.data_formats.base_data_classes import CompletionTopLogprobs
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.prompt import PromptRevision
from py_fade.controllers.text_generation_controller import TextGenerationController
from py_fade.providers.providers_manager import MappedModel
from py_fade.providers.mock_provider import MockLLMProvider

from tests.helpers.data_helpers import create_test_single_position_token


def create_completion_with_logprobs(dataset, prompt_revision, completion_text: str, model_id: str):
    """
    Create a completion with both sampled and alternative logprobs for testing.

    Returns tuple of (completion, logprobs_entry).
    """
    session = dataset.get_session()

    # Create completion
    sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()
    completion = PromptCompletion(prompt_revision_id=prompt_revision.id, sha256=sha256, model_id=model_id, temperature=0.7, top_k=40,
                                  completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                  context_length=2048, max_tokens=512, is_archived=False)
    session.add(completion)
    session.commit()

    # Create sampled logprobs that match the completion text exactly
    # Split the completion text into tokens
    tokens = [completion_text[:len(completion_text) // 2], completion_text[len(completion_text) // 2:]]
    sampled_logprobs_list = [
        create_test_single_position_token(tokens[0], -0.5).to_dict(),
        create_test_single_position_token(tokens[1], -0.8).to_dict()
    ]

    # Create alternative logprobs (top-k alternatives for each position)
    alternative_logprobs = CompletionTopLogprobs([[
        create_test_single_position_token(tokens[0], -0.5),
        create_test_single_position_token("Sample", -1.2),
        create_test_single_position_token("Example", -1.5),
    ],
                                                  [
                                                      create_test_single_position_token(tokens[1], -0.8),
                                                      create_test_single_position_token(" response", -1.1),
                                                      create_test_single_position_token(" answer", -1.3),
                                                  ]])

    # Compress and store alternative logprobs
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(alternative_logprobs)

    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
    logprobs_entry = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=model_id, sampled_logprobs=None,
                                              sampled_logprobs_json=sampled_logprobs_list, alternative_logprobs=None,
                                              alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=-0.8, avg_logprob=-0.65)
    # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
    session.add(logprobs_entry)
    session.commit()

    return completion, logprobs_entry


class TestArchiveCleanAlternativeLogprobs:
    """
    Test suite for cleaning alternative logprobs when archiving completions.
    """

    def test_clean_alternative_logprobs_removes_alternatives(self, temp_dataset):
        """
        Test that cleaning alternative logprobs removes alternative tokens while preserving sampled tokens.
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        completion, logprobs_entry = create_completion_with_logprobs(temp_dataset, prompt, "Test completion", "test-model")

        # Verify alternative logprobs exist before cleaning
        assert logprobs_entry.alternative_logprobs is not None
        assert len(logprobs_entry.alternative_logprobs) == 2
        assert len(logprobs_entry.alternative_logprobs[0]) == 3  # 3 alternatives for first token

        # Clean alternative logprobs
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Verify alternative logprobs are cleaned (empty)
        # Need to refresh from database to see changes
        temp_dataset.session.refresh(logprobs_entry)
        assert logprobs_entry.alternative_logprobs is not None
        assert len(logprobs_entry.alternative_logprobs) == 0

        # Verify sampled logprobs are still present
        assert logprobs_entry.sampled_logprobs is not None
        assert len(logprobs_entry.sampled_logprobs) == 2
        # The tokens should match the split completion text
        reconstructed = logprobs_entry.sampled_logprobs[0].token_str + logprobs_entry.sampled_logprobs[1].token_str
        assert reconstructed == "Test completion"

    def test_archive_completion_cleans_alternative_logprobs(self, temp_dataset):
        """
        Test that archiving a completion automatically cleans alternative logprobs.
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        completion, logprobs_entry = create_completion_with_logprobs(temp_dataset, prompt, "Test completion", "test-model")

        # Verify alternative logprobs exist before archiving
        assert len(logprobs_entry.alternative_logprobs) > 0

        # Archive the completion (simulating what happens in the GUI)
        completion.is_archived = True
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Verify completion is archived
        assert completion.is_archived is True

        # Verify alternative logprobs are cleaned
        temp_dataset.session.refresh(logprobs_entry)
        assert len(logprobs_entry.alternative_logprobs) == 0

        # Verify sampled logprobs are preserved
        assert len(logprobs_entry.sampled_logprobs) == 2

    def test_unarchive_does_not_restore_alternative_logprobs(self, temp_dataset):
        """
        Test that unarchiving a completion does not restore alternative logprobs.

        Once alternative logprobs are cleaned, they are gone permanently.
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        completion, logprobs_entry = create_completion_with_logprobs(temp_dataset, prompt, "Test completion", "test-model")

        # Archive and clean
        completion.is_archived = True
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Unarchive
        completion.is_archived = False
        temp_dataset.commit()

        # Verify alternative logprobs are still empty (not restored)
        temp_dataset.session.refresh(logprobs_entry)
        assert len(logprobs_entry.alternative_logprobs) == 0

        # Verify sampled logprobs are still present
        assert len(logprobs_entry.sampled_logprobs) == 2

    def test_clean_alternative_logprobs_with_multiple_logprobs_entries(self, temp_dataset):
        """
        Test cleaning alternative logprobs when a completion has multiple logprobs entries (multi-model).
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        completion, logprobs_entry1 = create_completion_with_logprobs(temp_dataset, prompt, "Test completion", "model-1")

        # Add second logprobs entry for different model
        session = temp_dataset.get_session()
        sampled_logprobs_list2 = [
            create_test_single_position_token("Test", -0.6).to_dict(),
            create_test_single_position_token(" completion", -0.9).to_dict()
        ]
        alternative_logprobs2 = CompletionTopLogprobs([[
            create_test_single_position_token("Test", -0.6),
            create_test_single_position_token("Demo", -1.3),
        ], [
            create_test_single_position_token(" completion", -0.9),
            create_test_single_position_token(" text", -1.2),
        ]])
        alternative_logprobs_bin2 = PromptCompletionLogprobs.compress_alternative_logprobs(alternative_logprobs2)

        # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
        logprobs_entry2 = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id="model-2", sampled_logprobs=None,
                                                   sampled_logprobs_json=sampled_logprobs_list2, alternative_logprobs=None,
                                                   alternative_logprobs_bin=alternative_logprobs_bin2, min_logprob=-0.9, avg_logprob=-0.75)
        # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
        session.add(logprobs_entry2)
        session.commit()

        # Clean alternative logprobs
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Verify both entries have cleaned alternative logprobs
        temp_dataset.session.refresh(logprobs_entry1)
        temp_dataset.session.refresh(logprobs_entry2)
        assert len(logprobs_entry1.alternative_logprobs) == 0
        assert len(logprobs_entry2.alternative_logprobs) == 0

        # Verify both entries still have sampled logprobs
        assert len(logprobs_entry1.sampled_logprobs) == 2
        assert len(logprobs_entry2.sampled_logprobs) == 2

    def test_clean_alternative_logprobs_with_no_logprobs(self, temp_dataset):
        """
        Test that cleaning alternative logprobs on a completion with no logprobs doesn't raise errors.
        """
        # Create completion without logprobs
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        session = temp_dataset.get_session()

        sha256 = hashlib.sha256("Test completion".encode("utf-8")).hexdigest()
        completion = PromptCompletion(prompt_revision_id=prompt.id, sha256=sha256, model_id="test-model", temperature=0.7, top_k=40,
                                      completion_text="Test completion", tags={}, prefill=None, beam_token=None, is_truncated=False,
                                      context_length=2048, max_tokens=512, is_archived=False)
        session.add(completion)
        session.commit()

        # This should not raise any errors
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Verify completion is still valid
        assert completion.completion_text == "Test completion"


class TestArchiveExcludeFromCache:
    """
    Test suite for excluding archived completions from generation cache.
    """

    def test_archived_completions_not_loaded_in_cache(self, temp_dataset, app_with_dataset):
        """
        Test that archived completions are not loaded into TextGenerationController cache.
        """
        # Create test data with multiple completions
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt for cache", 2048, 512)

        # Create non-archived completion
        completion1, _ = create_completion_with_logprobs(temp_dataset, prompt, "Active completion", "test-model")
        completion1.is_archived = False
        temp_dataset.commit()

        # Create archived completion
        completion2, _ = create_completion_with_logprobs(temp_dataset, prompt, "Archived completion", "test-model")
        completion2.is_archived = True
        completion2.clean_alternative_logprobs()
        temp_dataset.commit()

        # Create another non-archived completion
        completion3, _ = create_completion_with_logprobs(temp_dataset, prompt, "Another active completion", "test-model")
        completion3.is_archived = False
        temp_dataset.commit()

        # Create text generation controller and load cache
        mock_provider = MockLLMProvider()
        mapped_model = MappedModel("test-model", mock_provider)
        controller = TextGenerationController(app_with_dataset, mapped_model, temp_dataset, prompt)
        controller.load_cache()

        # Verify only non-archived completions are loaded
        assert len(controller.all_completions) == 2
        completion_texts = [c.completion_text for c in controller.all_completions]
        assert "Active completion" in completion_texts
        assert "Another active completion" in completion_texts
        assert "Archived completion" not in completion_texts

    def test_get_beams_excludes_archived(self, temp_dataset):
        """
        Test that get_beams_for_prompt_and_model excludes archived completions.
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt for beams", 2048, 512)

        # Create non-archived completion
        completion1, _ = create_completion_with_logprobs(temp_dataset, prompt, "Active beam", "beam-model")
        completion1.is_archived = False
        temp_dataset.commit()

        # Create archived completion
        completion2, _ = create_completion_with_logprobs(temp_dataset, prompt, "Archived beam", "beam-model")
        completion2.is_archived = True
        temp_dataset.commit()

        # Get beams
        beams = temp_dataset.get_beams_for_prompt_and_model(prompt, "beam-model")

        # Verify only non-archived beam is returned
        assert len(beams) == 1
        assert beams[0].completion_text == "Active beam"

    def test_archive_then_unarchive_still_excluded_from_cache(self, temp_dataset, app_with_dataset):
        """
        Test that a completion archived and then unarchived is loaded back into cache.

        Note: Alternative logprobs are not restored, but the completion itself is active again
        and can still be used for caching (sampled logprobs are sufficient for full_response_logprobs check).
        """
        # Create test data
        prompt = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 512)
        completion, logprobs_entry = create_completion_with_logprobs(temp_dataset, prompt, "Test completion", "test-model")

        # Archive and clean
        completion.is_archived = True
        completion.clean_alternative_logprobs()
        temp_dataset.commit()

        # Verify not in cache when archived
        mock_provider = MockLLMProvider()
        mapped_model = MappedModel("test-model", mock_provider)
        controller = TextGenerationController(app_with_dataset, mapped_model, temp_dataset, prompt)
        controller.load_cache()
        assert len(controller.all_completions) == 0

        # Unarchive
        completion.is_archived = False
        temp_dataset.commit()

        # Verify now in cache when unarchived
        # Even without alternative logprobs, the completion is still useful because sampled logprobs
        # are sufficient for check_full_response_logprobs()
        controller2 = TextGenerationController(app_with_dataset, mapped_model, temp_dataset, prompt)
        controller2.load_cache()
        assert len(controller2.all_completions) == 1
        assert controller2.all_completions[0].completion_text == "Test completion"

        # Verify alternative logprobs are still empty (not restored)
        temp_dataset.session.refresh(logprobs_entry)
        assert len(logprobs_entry.alternative_logprobs) == 0
