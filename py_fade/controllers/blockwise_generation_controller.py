"""
Controller logic for blockwise (paragraph-by-paragraph) text generation.

Handles shadow-prefill prompt construction, generate-to-newline logic,
automatic deduplication, and stub template interface for instruction-following regeneration.

Key classes: `BlockCandidate`, `BlockwiseGenerationController`
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from py_fade.data_formats.base_data_classes import (CommonConversation, CompletionPrefill)
from py_fade.providers.flat_prefix_template import parse_flat_prefix_string
from py_fade.providers.llm_response import LLMResponse

if TYPE_CHECKING:
    from py_fade.providers.providers_manager import MappedModel


@dataclass
class BlockCandidate:
    """
    A single candidate block generated during blockwise generation.

    Holds the text, word count, token count, and the raw LLM response.
    """

    text: str
    word_count: int
    token_count: int
    response: LLMResponse | None = None


def _default_rewrite_template(original_prompt: str, original_block: str, instruction: str) -> CommonConversation:
    """
    Default stub template for instruction-following block rewriting.

    Creates a separate isolated prompt that asks the model to rewrite a block
    according to the given instruction. The specific template text is a stub
    placeholder — the real template is out of scope for this issue.

    Args:
        original_prompt: The original user prompt text.
        original_block: The original block text to rewrite.
        instruction: The rewriting instruction.

    Returns:
        CommonConversation with the rewriting prompt.
    """
    rewrite_prompt = (f"Rewrite the following text according to the instruction.\n\n"
                      f"Original prompt: {original_prompt}\n\n"
                      f"Original text: {original_block}\n\n"
                      f"Instruction: {instruction}")
    return CommonConversation.from_single_user(rewrite_prompt)


@dataclass
class BlockwiseGenerationController:
    """
    Orchestrate blockwise text generation with shadow-prefill prompt construction.

    All state is transient (in-memory only). The only persistence action is the
    user saving the current completion via the UI.

    The prompt sent to the model differs from the final sample output:
    - User message: original_prompt + global_instructions
    - Assistant prefill: accepted_blocks_text + block_instructions + manual_prefix
    Block instructions and manual prefix are scrubbed from the final output.

    Attributes:
        mapped_model: The model used for generation.
        original_prompt: The original sample prompt text.
        accepted_blocks: List of accepted block texts.
        candidates: List of current candidate blocks.
        global_instructions: Shadow addendum appended to user message.
        block_instructions: Shadow text injected into assistant prefill.
        manual_prefix: Manual text injected at start of block in prefill.
        temperature: Generation temperature.
        top_k: Top-k sampling parameter.
        rewrite_template: Callable for instruction-following regeneration prompts.
    """

    mapped_model: "MappedModel"
    original_prompt: str
    accepted_blocks: list[str] = field(default_factory=list)
    candidates: list[BlockCandidate] = field(default_factory=list)
    global_instructions: str = ""
    block_instructions: str = ""
    manual_prefix: str = ""
    temperature: float = 0.7
    top_k: int = 40
    context_length: int = 2048
    max_tokens: int = 256
    rewrite_template: Callable[[str, str, str], CommonConversation] = _default_rewrite_template

    def __post_init__(self):
        """Initialize logger after dataclass init."""
        self.log = logging.getLogger("BlockwiseGenerationController")

    @property
    def accepted_text(self) -> str:
        """Return concatenated text of all accepted blocks."""
        return "".join(self.accepted_blocks)

    def build_generation_conversation(self) -> CommonConversation:
        """
        Build the conversation for block generation.

        User message = original_prompt + global_instructions.
        Does NOT include the assistant prefill — that is passed separately.

        Returns:
            CommonConversation with the constructed prompt.
        """
        user_content = self.original_prompt
        if self.global_instructions.strip():
            user_content = f"{self.original_prompt}\n\n{self.global_instructions}"
        return CommonConversation.from_single_user(user_content)

    def build_prefill_text(self) -> str:
        """
        Build the assistant prefill text for generation.

        Structure: accepted_blocks_text + block_instructions + manual_prefix.
        Block instructions and manual prefix are scrubbed from final output.

        Returns:
            The prefill text string.
        """
        parts = [self.accepted_text]
        if self.block_instructions.strip():
            parts.append(self.block_instructions)
        if self.manual_prefix.strip():
            parts.append(self.manual_prefix)
        return "".join(parts)

    def _extract_block_text(self, full_text: str) -> str:
        """
        Extract the block text from a full generation response.

        A block is text up to and including the next newline character.
        The accepted text, block instructions, and manual prefix are scrubbed.

        Args:
            full_text: The full completion text from the model response.

        Returns:
            The extracted block text (up to and including the first newline).
        """
        # Remove the prefill portion to get only the newly generated part
        prefill = self.build_prefill_text()
        if full_text.startswith(prefill):
            generated = full_text[len(prefill):]
        else:
            # Fallback: try to strip just accepted text
            accepted = self.accepted_text
            if full_text.startswith(accepted):
                generated = full_text[len(accepted):]
            else:
                generated = full_text

        if not generated:
            return ""

        # Find the first newline — block boundary
        newline_idx = generated.find("\n")
        if newline_idx >= 0:
            return generated[:newline_idx + 1]
        # No newline found — entire generated text is the block
        return generated

    def _is_duplicate(self, block_text: str) -> bool:
        """
        Check if a block text exactly matches any existing candidate.

        Args:
            block_text: The block text to check.

        Returns:
            True if a duplicate exists.
        """
        return any(c.text == block_text for c in self.candidates)

    def generate_candidates(self, width: int, on_candidate: Callable[[BlockCandidate], None] | None = None,
                            on_check_stop: Callable[[], bool] | None = None) -> list[BlockCandidate]:
        """
        Generate `width` candidate blocks sequentially.

        Each candidate is generated until the next newline token.
        Automatic deduplication prevents adding candidates with identical text.
        New candidates are appended at the end, preserving existing candidates.

        Args:
            width: Number of candidate blocks to generate.
            on_candidate: Optional callback invoked for each new candidate.
            on_check_stop: Optional callback to check if generation should stop.

        Returns:
            List of newly generated (non-duplicate) candidates.
        """
        conversation = self.build_generation_conversation()
        prefill_text = self.build_prefill_text()

        completion_prefill = None
        if prefill_text:
            completion_prefill = CompletionPrefill(prefill_text=prefill_text, prefill_tokenized=None)

        new_candidates = []
        for i in range(width):
            if on_check_stop and on_check_stop():
                self.log.info("Block generation stopped by request at candidate %d/%d.", i, width)
                break

            try:
                response = self.mapped_model.generate(
                    prompt=conversation,
                    prefill=completion_prefill,
                    temperature=self.temperature,
                    top_k=self.top_k,
                    context_length=self.context_length,
                    max_tokens=self.max_tokens,
                )

                block_text = self._extract_block_text(response.completion_text)
                if not block_text:
                    self.log.warning("Empty block generated at candidate %d/%d, skipping.", i + 1, width)
                    continue

                if self._is_duplicate(block_text):
                    self.log.debug("Duplicate block at candidate %d/%d, skipping: %s", i + 1, width, block_text[:50])
                    continue

                candidate = BlockCandidate(
                    text=block_text,
                    word_count=len(block_text.split()),
                    token_count=len(response.logprobs.sampled_logprobs) if response.logprobs else 0,
                    response=response,
                )
                self.candidates.append(candidate)
                new_candidates.append(candidate)

                if on_candidate:
                    on_candidate(candidate)

            except Exception:  # pylint: disable=broad-except
                self.log.exception("Error generating candidate %d/%d.", i + 1, width)

        return new_candidates

    def accept_candidate(self, candidate: BlockCandidate) -> str:
        """
        Accept a candidate block, append it to the accepted blocks, and clear all candidates.

        Args:
            candidate: The candidate to accept.

        Returns:
            The updated accepted text.
        """
        self.accepted_blocks.append(candidate.text)
        self.candidates.clear()
        self.log.info("Accepted block %d: %s", len(self.accepted_blocks), candidate.text[:50])
        return self.accepted_text

    def rewrite_block(self, original_candidate: BlockCandidate, instruction: str) -> BlockCandidate | None:
        """
        Generate a rewritten version of a block using instruction-following regeneration.

        Uses an isolated prompt context with the rewrite template.
        The new candidate is inserted immediately before the original in sort order.

        Args:
            original_candidate: The candidate to rewrite.
            instruction: The rewriting instruction.

        Returns:
            A new BlockCandidate with the rewritten text, or None on failure.
        """
        try:
            rewrite_conversation = self.rewrite_template(self.original_prompt, original_candidate.text, instruction)
            response = self.mapped_model.generate(
                prompt=rewrite_conversation,
                temperature=self.temperature,
                top_k=self.top_k,
                context_length=self.context_length,
                max_tokens=self.max_tokens,
            )

            block_text = response.generated_part_text or response.completion_text
            # Trim to first newline for block boundary
            newline_idx = block_text.find("\n")
            if newline_idx >= 0:
                block_text = block_text[:newline_idx + 1]

            if not block_text:
                self.log.warning("Empty rewrite result.")
                return None

            candidate = BlockCandidate(
                text=block_text,
                word_count=len(block_text.split()),
                token_count=len(response.logprobs.sampled_logprobs) if response.logprobs else 0,
                response=response,
            )

            # Insert before the original candidate
            idx = self.candidates.index(original_candidate) if original_candidate in self.candidates else len(self.candidates)
            self.candidates.insert(idx, candidate)
            return candidate

        except Exception:  # pylint: disable=broad-except
            self.log.exception("Error rewriting block.")
            return None

    def make_shorter(self, original_candidate: BlockCandidate) -> BlockCandidate | None:
        """
        Shortcut for instruction-following regeneration with a 'make more concise' instruction.

        Args:
            original_candidate: The candidate to make shorter.

        Returns:
            A new BlockCandidate with the shortened text, or None on failure.
        """
        return self.rewrite_block(original_candidate, "Make this more concise and shorter while keeping the key meaning.")

    def make_longer(self, original_candidate: BlockCandidate) -> BlockCandidate | None:
        """
        Shortcut for instruction-following regeneration with an 'expand with more detail' instruction.

        Args:
            original_candidate: The candidate to make longer.

        Returns:
            A new BlockCandidate with the expanded text, or None on failure.
        """
        return self.rewrite_block(original_candidate, "Expand this with more detail and elaboration while maintaining the same style.")

    def create_edited_candidate(self, original_candidate: BlockCandidate, edited_text: str) -> BlockCandidate:
        """
        Create a new candidate from edited text, inserting it before the original.

        The original candidate remains immutable; the new candidate is a fresh block.

        Args:
            original_candidate: The original candidate being edited.
            edited_text: The new text after editing.

        Returns:
            The new BlockCandidate with the edited text.
        """
        candidate = BlockCandidate(
            text=edited_text,
            word_count=len(edited_text.split()),
            token_count=0,
            response=None,
        )
        # Insert before the original
        idx = self.candidates.index(original_candidate) if original_candidate in self.candidates else len(self.candidates)
        self.candidates.insert(idx, candidate)
        return candidate

    def build_save_response(self) -> LLMResponse:
        """
        Build an LLMResponse from the current accepted text for saving.

        Returns:
            An LLMResponse suitable for saving via WidgetSample.add_completion().
        """
        conversation = parse_flat_prefix_string(self.original_prompt)
        return LLMResponse(
            model_id=self.mapped_model.model_id,
            prompt_conversation=conversation,
            completion_text=self.accepted_text,
            generated_part_text=self.accepted_text,
            temperature=self.temperature,
            top_k=self.top_k,
            context_length=self.context_length,
            max_tokens=self.max_tokens,
            prefill=None,
            beam_token=None,
            logprobs=None,
            is_truncated=False,
            is_manual=True,
        )
