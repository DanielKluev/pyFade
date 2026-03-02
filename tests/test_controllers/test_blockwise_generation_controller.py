"""
Tests for the BlockwiseGenerationController.

Covers prompt construction, block extraction, deduplication,
candidate generation, block acceptance, rewriting, and save response building.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from py_fade.controllers.blockwise_generation_controller import (
    BlockCandidate,
    BlockwiseGenerationController,
    _default_rewrite_template,
)
from py_fade.data_formats.base_data_classes import CommonConversation, CompletionPrefill
from py_fade.providers.llm_response import LLMResponse
from py_fade.providers.mock_provider import MockLLMProvider
from py_fade.providers.providers_manager import MappedModel

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mapped_model() -> MappedModel:
    """
    Create a real MappedModel with MockLLMProvider for deterministic tests.
    """
    provider = MockLLMProvider()
    return MappedModel("mock-echo-model", provider)


@pytest.fixture
def controller(mock_mapped_model: MappedModel) -> BlockwiseGenerationController:
    """
    Create a BlockwiseGenerationController with default settings.
    """
    return BlockwiseGenerationController(
        mapped_model=mock_mapped_model,
        original_prompt="Write a short story about a robot.",
    )


# ---------------------------------------------------------------------------
# Test prompt and prefill construction
# ---------------------------------------------------------------------------


class TestPromptConstruction:
    """
    Test prompt and prefill construction for blockwise generation.
    """

    def test_build_conversation_without_instructions(self, controller: BlockwiseGenerationController) -> None:
        """
        Building conversation without global instructions uses only the original prompt.
        """
        conv = controller.build_generation_conversation()
        messages = conv.as_list()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Write a short story about a robot."

    def test_build_conversation_with_global_instructions(self, controller: BlockwiseGenerationController) -> None:
        """
        Building conversation with global instructions appends them to the user message.
        """
        controller.global_instructions = "Keep it under 100 words."
        conv = controller.build_generation_conversation()
        messages = conv.as_list()
        assert "Keep it under 100 words." in messages[0]["content"]
        assert "Write a short story about a robot." in messages[0]["content"]

    def test_build_prefill_empty(self, controller: BlockwiseGenerationController) -> None:
        """
        Building prefill with no accepted blocks and no instructions returns empty string.
        """
        assert controller.build_prefill_text() == ""

    def test_build_prefill_with_accepted_blocks(self, controller: BlockwiseGenerationController) -> None:
        """
        Building prefill includes accepted block text.
        """
        controller.accepted_blocks = ["First paragraph.\n", "Second paragraph.\n"]
        prefill = controller.build_prefill_text()
        assert prefill.startswith("First paragraph.\n")
        assert "Second paragraph.\n" in prefill

    def test_build_prefill_with_all_components(self, controller: BlockwiseGenerationController) -> None:
        """
        Building prefill includes accepted blocks, block instructions, and manual prefix.
        """
        controller.accepted_blocks = ["Block one.\n"]
        controller.block_instructions = "[Write in formal style]"
        controller.manual_prefix = "The next part"
        prefill = controller.build_prefill_text()
        assert "Block one.\n" in prefill
        assert "[Write in formal style]" in prefill
        assert "The next part" in prefill


# ---------------------------------------------------------------------------
# Test block text extraction
# ---------------------------------------------------------------------------


class TestBlockExtraction:
    """
    Test block text extraction from model responses.
    """

    def test_extract_block_with_newline(self, controller: BlockwiseGenerationController) -> None:
        """
        Extracting a block from text containing a newline stops at the newline.
        """
        text = "First line.\nSecond line.\n"
        result = controller._extract_block_text(text)  # pylint: disable=protected-access
        assert result == "First line.\n"

    def test_extract_block_without_newline(self, controller: BlockwiseGenerationController) -> None:
        """
        Extracting a block from text without newline returns the entire text.
        """
        text = "Just one line without newline"
        result = controller._extract_block_text(text)  # pylint: disable=protected-access
        assert result == "Just one line without newline"

    def test_extract_block_with_prefill(self, controller: BlockwiseGenerationController) -> None:
        """
        Extracting a block with accepted text prefix strips the prefix.
        """
        controller.accepted_blocks = ["Already accepted.\n"]
        text = "Already accepted.\nNew block text.\nMore text."
        result = controller._extract_block_text(text)  # pylint: disable=protected-access
        assert result == "New block text.\n"

    def test_extract_block_empty_generated(self, controller: BlockwiseGenerationController) -> None:
        """
        Extracting a block when generated text is empty returns empty string.
        """
        controller.accepted_blocks = ["Full text"]
        text = "Full text"
        result = controller._extract_block_text(text)  # pylint: disable=protected-access
        assert result == ""


# ---------------------------------------------------------------------------
# Test deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """
    Test automatic deduplication of candidate blocks.
    """

    def test_no_duplicate_for_unique_text(self, controller: BlockwiseGenerationController) -> None:
        """
        Unique text is not considered a duplicate.
        """
        controller.candidates.append(BlockCandidate(text="Existing block.\n", word_count=2, token_count=3))
        assert not controller._is_duplicate("Different block.\n")  # pylint: disable=protected-access

    def test_duplicate_detected(self, controller: BlockwiseGenerationController) -> None:
        """
        Exact matching text is detected as a duplicate.
        """
        controller.candidates.append(BlockCandidate(text="Same text.\n", word_count=2, token_count=3))
        assert controller._is_duplicate("Same text.\n")  # pylint: disable=protected-access

    def test_empty_candidates_no_duplicate(self, controller: BlockwiseGenerationController) -> None:
        """
        No duplicates exist when candidate list is empty.
        """
        assert not controller._is_duplicate("Any text.\n")  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Test candidate generation
# ---------------------------------------------------------------------------


class TestCandidateGeneration:
    """
    Test generation of block candidates using mock provider.
    """

    def test_generate_candidates_returns_blocks(self, controller: BlockwiseGenerationController) -> None:
        """
        Generating candidates returns a list of BlockCandidate objects.
        """
        candidates = controller.generate_candidates(width=2)
        assert len(candidates) > 0
        for c in candidates:
            assert isinstance(c, BlockCandidate)
            assert c.text  # Non-empty text

    def test_generate_candidates_appends_to_existing(self, controller: BlockwiseGenerationController) -> None:
        """
        Generating more candidates does not remove existing ones.
        """
        controller.generate_candidates(width=1)
        first_count = len(controller.candidates)
        assert first_count >= 1

        controller.generate_candidates(width=1)
        # Should have at least the same or more candidates (dedup may prevent some)
        assert len(controller.candidates) >= first_count

    def test_generate_candidates_deduplication(self, controller: BlockwiseGenerationController) -> None:
        """
        Duplicate candidates are not added.

        Since mock provider is deterministic, generating the same width twice
        should not add duplicates.
        """
        controller.generate_candidates(width=2)
        count_after_first = len(controller.candidates)

        controller.generate_candidates(width=2)
        # Should have the same count (all duplicates filtered)
        assert len(controller.candidates) == count_after_first

    def test_generate_candidates_with_stop_callback(self, controller: BlockwiseGenerationController) -> None:
        """
        Generation stops when on_check_stop returns True.
        """
        call_count = 0

        def stop_after_one() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        candidates = controller.generate_candidates(width=5, on_check_stop=stop_after_one)
        assert len(candidates) <= 2  # At most 1-2 candidates before stop

    def test_generate_candidates_on_candidate_callback(self, controller: BlockwiseGenerationController) -> None:
        """
        The on_candidate callback is invoked for each new candidate.
        """
        received = []
        controller.generate_candidates(width=2, on_candidate=lambda c: received.append(c))
        assert len(received) > 0
        for c in received:
            assert isinstance(c, BlockCandidate)


# ---------------------------------------------------------------------------
# Test block acceptance
# ---------------------------------------------------------------------------


class TestBlockAcceptance:
    """
    Test accepting a candidate block.
    """

    def test_accept_candidate_appends_text(self, controller: BlockwiseGenerationController) -> None:
        """
        Accepting a candidate appends its text to accepted_blocks.
        """
        candidate = BlockCandidate(text="Accepted paragraph.\n", word_count=2, token_count=4)
        controller.candidates.append(candidate)

        result = controller.accept_candidate(candidate)
        assert "Accepted paragraph.\n" in result
        assert len(controller.accepted_blocks) == 1

    def test_accept_candidate_clears_candidates(self, controller: BlockwiseGenerationController) -> None:
        """
        Accepting a candidate clears all current candidates.
        """
        controller.candidates.extend([
            BlockCandidate(text="A.\n", word_count=1, token_count=1),
            BlockCandidate(text="B.\n", word_count=1, token_count=1),
        ])
        controller.accept_candidate(controller.candidates[0])
        assert len(controller.candidates) == 0

    def test_accept_multiple_blocks(self, controller: BlockwiseGenerationController) -> None:
        """
        Accepting multiple blocks sequentially builds up the accepted text.
        """
        c1 = BlockCandidate(text="First.\n", word_count=1, token_count=1)
        c2 = BlockCandidate(text="Second.\n", word_count=1, token_count=1)

        controller.candidates.append(c1)
        controller.accept_candidate(c1)
        assert controller.accepted_text == "First.\n"

        controller.candidates.append(c2)
        controller.accept_candidate(c2)
        assert controller.accepted_text == "First.\nSecond.\n"

    def test_accepted_text_property(self, controller: BlockwiseGenerationController) -> None:
        """
        The accepted_text property concatenates all accepted blocks.
        """
        controller.accepted_blocks = ["A\n", "B\n", "C\n"]
        assert controller.accepted_text == "A\nB\nC\n"


# ---------------------------------------------------------------------------
# Test rewriting
# ---------------------------------------------------------------------------


class TestRewriting:
    """
    Test instruction-following regeneration (rewriting).
    """

    def test_rewrite_block_returns_candidate(self, controller: BlockwiseGenerationController) -> None:
        """
        Rewriting a block returns a new BlockCandidate.
        """
        original = BlockCandidate(text="Original text.\n", word_count=2, token_count=3)
        controller.candidates.append(original)

        result = controller.rewrite_block(original, "Make it more formal")
        assert result is not None
        assert isinstance(result, BlockCandidate)
        assert result.text  # Non-empty

    def test_rewrite_inserts_before_original(self, controller: BlockwiseGenerationController) -> None:
        """
        Rewritten block is inserted before the original in the candidates list.
        """
        c1 = BlockCandidate(text="First.\n", word_count=1, token_count=1)
        c2 = BlockCandidate(text="Second.\n", word_count=1, token_count=1)
        controller.candidates = [c1, c2]

        result = controller.rewrite_block(c2, "Rephrase")
        assert result is not None
        idx_rewrite = controller.candidates.index(result)
        idx_original = controller.candidates.index(c2)
        assert idx_rewrite < idx_original

    def test_make_shorter(self, controller: BlockwiseGenerationController) -> None:
        """
        make_shorter() returns a new candidate.
        """
        original = BlockCandidate(text="Some long text.\n", word_count=3, token_count=5)
        controller.candidates.append(original)
        result = controller.make_shorter(original)
        assert result is not None

    def test_make_longer(self, controller: BlockwiseGenerationController) -> None:
        """
        make_longer() returns a new candidate.
        """
        original = BlockCandidate(text="Short.\n", word_count=1, token_count=2)
        controller.candidates.append(original)
        result = controller.make_longer(original)
        assert result is not None


# ---------------------------------------------------------------------------
# Test editing
# ---------------------------------------------------------------------------


class TestEditing:
    """
    Test candidate editing.
    """

    def test_create_edited_candidate(self, controller: BlockwiseGenerationController) -> None:
        """
        Creating an edited candidate adds a new candidate with edited text.
        """
        original = BlockCandidate(text="Original.\n", word_count=1, token_count=2)
        controller.candidates.append(original)

        edited = controller.create_edited_candidate(original, "Edited version.\n")
        assert edited.text == "Edited version.\n"
        assert edited in controller.candidates

    def test_edited_candidate_inserted_before_original(self, controller: BlockwiseGenerationController) -> None:
        """
        Edited candidate is inserted before the original.
        """
        original = BlockCandidate(text="Original.\n", word_count=1, token_count=2)
        controller.candidates.append(original)

        edited = controller.create_edited_candidate(original, "Edited.\n")
        assert controller.candidates.index(edited) < controller.candidates.index(original)

    def test_edited_candidate_word_count(self, controller: BlockwiseGenerationController) -> None:
        """
        Edited candidate has correct word count.
        """
        original = BlockCandidate(text="One.\n", word_count=1, token_count=1)
        controller.candidates.append(original)
        edited = controller.create_edited_candidate(original, "One two three.\n")
        assert edited.word_count == 3


# ---------------------------------------------------------------------------
# Test save response building
# ---------------------------------------------------------------------------


class TestSaveResponse:
    """
    Test building save response for persistence.
    """

    def test_build_save_response_type(self, controller: BlockwiseGenerationController) -> None:
        """
        build_save_response() returns an LLMResponse.
        """
        controller.accepted_blocks = ["Hello world.\n"]
        response = controller.build_save_response()
        assert isinstance(response, LLMResponse)

    def test_build_save_response_text(self, controller: BlockwiseGenerationController) -> None:
        """
        build_save_response() includes all accepted text.
        """
        controller.accepted_blocks = ["First.\n", "Second.\n"]
        response = controller.build_save_response()
        assert response.completion_text == "First.\nSecond.\n"

    def test_build_save_response_model_id(self, controller: BlockwiseGenerationController) -> None:
        """
        build_save_response() uses the mapped model's ID.
        """
        controller.accepted_blocks = ["Text.\n"]
        response = controller.build_save_response()
        assert response.model_id == "mock-echo-model"

    def test_build_save_response_is_manual(self, controller: BlockwiseGenerationController) -> None:
        """
        build_save_response() marks the response as manual.
        """
        controller.accepted_blocks = ["Text.\n"]
        response = controller.build_save_response()
        assert response.is_manual is True


# ---------------------------------------------------------------------------
# Test default rewrite template
# ---------------------------------------------------------------------------


class TestDefaultRewriteTemplate:
    """
    Test the default stub rewrite template.
    """

    def test_returns_conversation(self) -> None:
        """
        Default template returns a CommonConversation.
        """
        result = _default_rewrite_template("prompt", "block text", "make shorter")
        assert isinstance(result, CommonConversation)
        messages = result.as_list()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_includes_all_components(self) -> None:
        """
        Default template includes original prompt, block text, and instruction.
        """
        result = _default_rewrite_template("My prompt", "My block", "Rephrase")
        content = result.as_list()[0]["content"]
        assert "My prompt" in content
        assert "My block" in content
        assert "Rephrase" in content
