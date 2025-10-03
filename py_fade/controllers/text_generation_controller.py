"""Controller logic for orchestrating text generation workflows."""

import logging
import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from py_fade.data_formats.base_data_classes import (CommonConversation, CommonCompletionLogprobs, CommonCompletionProtocol,
                                                    CompletionTokenLogprobs, CompletionTopLogprobs, SinglePositionTopLogprobs,
                                                    SinglePositionToken, CompletionPrefill)
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.prompt import PromptRevision
from py_fade.providers.llm_response import LLMResponse
from py_fade.providers.flat_prefix_template import parse_flat_prefix_string

if TYPE_CHECKING:
    from py_fade.app import PyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.providers.providers_manager import MappedModel


@dataclass
class CompletionPrefix:
    """Cached metadata about a prefix used to seed beam search expansions."""

    prefix_text: str
    prefix_token_size: int
    sampled_logprobs: CompletionTokenLogprobs
    alternative_logprobs: CompletionTopLogprobs | None = None  # Alternative logprobs for each token position, if available

    @classmethod
    def try_get_from_response(cls, prefix_text: str, response: LLMResponse) -> "CompletionPrefix|None":
        """
        Try to extract CompletionPrefix from LLMResponse if possible.
        Response must contain logprobs for all tokens in the prefix.
        """
        if prefix_text and not response.completion_text.startswith(prefix_text):
            return None  # Prefix does not match

        if not response.check_full_response_logprobs() or not response.logprobs:
            return None  # Logprobs do not cover full response

        prefix_tokens_count = 0
        current_pos = 0
        for lp in response.logprobs.sampled_logprobs:
            if lp.token_str != prefix_text[current_pos:current_pos + len(lp.token_str)]:
                return None  # Token does not match prefix at this position
            current_pos += len(lp.token_str)
            prefix_tokens_count += 1
            if current_pos >= len(prefix_text):
                break

        if current_pos != len(prefix_text):
            return None  # Did not cover full prefix

        sampled_logprobs = CompletionTokenLogprobs(response.logprobs.sampled_logprobs[0:prefix_tokens_count])
        alternative_logprobs = None
        if response.logprobs.alternative_logprobs and len(response.logprobs.alternative_logprobs) >= prefix_tokens_count + 1:
            alternative_logprobs = CompletionTopLogprobs(response.logprobs.alternative_logprobs[0:prefix_tokens_count + 1])

        # Successfully matched full prefix with logprobs, return slice of logprobs
        return cls(
            prefix_text=prefix_text,
            prefix_token_size=prefix_tokens_count,
            sampled_logprobs=sampled_logprobs,
            alternative_logprobs=alternative_logprobs,
        )

    @classmethod
    def create_empty_prefix_from_response(cls, response: LLMResponse) -> "CompletionPrefix|None":
        """
        Create an empty CompletionPrefix from LLMResponse with no prefix text.
        Response must contain alternative logprobs for at least the first token.
        """
        if not response.logprobs or not response.logprobs.alternative_logprobs:
            return None  # No alternative logprobs available

        alternative_logprobs = CompletionTopLogprobs([response.logprobs.alternative_logprobs[0]])
        return cls(
            prefix_text="",
            prefix_token_size=0,
            sampled_logprobs=CompletionTokenLogprobs([]),
            alternative_logprobs=alternative_logprobs,
        )

    @classmethod
    def create_from_eval(cls, prefix_text: str, eval_logprobs: CommonCompletionLogprobs) -> "CompletionPrefix":
        """
        Create CompletionPrefix from evaluated logprobs for given prefix text.
        """
        # Count tokens in prefix text
        prefix_tokens_count = len(eval_logprobs.sampled_logprobs)
        return cls(
            prefix_text=prefix_text,
            prefix_token_size=prefix_tokens_count,
            sampled_logprobs=eval_logprobs.sampled_logprobs,
            alternative_logprobs=eval_logprobs.alternative_logprobs,
        )


class TextGenerationController:
    """Coordinate inference providers, dataset caching, and GUI callbacks."""

    app: "PyFadeApp"
    mapped_model: "MappedModel"
    prompt_revision: PromptRevision
    prompt_conversation: CommonConversation
    dataset: "DatasetDatabase"
    all_completions: list[LLMResponse]
    cached_prefixes: dict[str, CompletionPrefix]
    cache_by_hash: dict[str, LLMResponse]  # SHA256 hash of completion text -> LLMResponse
    zero_prefix: CompletionPrefix | None = None  # Cached empty prefix (first completion token)

    def __init__(self, app: "PyFadeApp", mapped_model: "MappedModel", dataset: "DatasetDatabase", prompt_revision: PromptRevision,
                 context_length: int | None = None) -> None:
        """
        Bind the controller to the owning app, dataset, and selected model.
        """
        self.log = logging.getLogger("TextGenerationController")
        self.app = app
        self.all_completions = []
        self.cached_prefixes = {}
        self.cache_by_hash = {}
        self.default_temperature = app.config.default_temperature
        self.default_top_k = app.config.default_top_k
        self.default_context_length = context_length or app.config.default_context_length
        self.default_max_tokens = app.config.default_max_tokens
        self.mapped_model = mapped_model
        self.provider = mapped_model.provider
        self.model_id = mapped_model.model_id
        self.dataset = dataset
        self.prompt_revision = prompt_revision
        self.prompt_conversation = parse_flat_prefix_string(self.prompt_revision.prompt_text)

    def load_cache(self):
        """
        Load completion cache to speed up generation from dataset.
        """
        self.log.info(
            "Loading cache for model %s and prompt revision %s",
            self.mapped_model.path,
            self.prompt_revision.id,
        )
        if not self.dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        # Populate with cached beams
        completions = self.dataset.get_beams_for_prompt_and_model(self.prompt_revision, self.mapped_model.model_id)
        for completion in completions:
            self.add_cached_completion(completion)

        self.log.info(
            "Populated completions cache with %d existing completions from dataset.",
            len(self.all_completions),
        )

    def add_cached_completion(self, completion: LLMResponse):
        """
        Add a new LLMResponse to the cache of completions.
        """
        if completion.model_id != self.model_id:
            return
        if not completion.check_full_response_logprobs():
            return
        completion_hash = hashlib.sha256(completion.completion_text.encode("utf-8")).hexdigest()
        if completion_hash in self.cache_by_hash:
            return  # Already cached
        self.all_completions.append(completion)
        self.cache_by_hash[completion_hash] = completion
        if not self.zero_prefix and completion.logprobs and completion.logprobs.alternative_logprobs:
            self.zero_prefix = CompletionPrefix.create_empty_prefix_from_response(completion)
            if self.zero_prefix:
                self.log.info("Cached zero prefix from existing completion.")
                self.cached_prefixes[""] = self.zero_prefix

    def generate(self, prefill: str | None = None, temperature: float | None = None, top_k: int | None = None,
                 context_length: int | None = None, max_tokens: int | None = None) -> LLMResponse:
        """
        Generate a new completion using the mapped model and provider.
        """
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": prefill,
            "temperature": temperature or self.default_temperature,
            "top_k": top_k or self.default_top_k,
            "context_length": context_length or self.default_context_length,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        response = self.mapped_model.generate(**generation_kwargs)
        self.add_cached_completion(response)
        return response

    def beam_out_on_token_one_level(self, prefix: str, width: int, length: int, *, beam_tokens: list[SinglePositionToken] | None = None,
                                    on_beam_completed: Callable[[LLMResponse], None] | None = None,
                                    on_check_stop: Callable[[], bool] | None = None) -> list[LLMResponse]:
        """
        Keep prefix fixed and expand the next token after prefix with ``width`` beams.
        Each beam spans up to ``length`` tokens.

        The method ensures prefix logprobs are known, evaluating them if required.
        It also ensures the next token logprobs are available up to ``width`` entries.

        Returns a list of completed beams (if any) and updates internal state.
        """
        # 1. Check if prefix logprobs are known. We only need selected token logprobs to
        #    calculate beam min_logprob scores. If missing, evaluate them using the provider.
        beam_prefix = self._find_beam_prefix(prefix)

        # 2. Check if we have logprobs for next token after prefix, up to ``width`` top_k
        #    token variants. If not, generate them using the provider.
        alternate_logprobs = self.fetch_next_token_logprobs_for_prefix(beam_prefix, width)
        if beam_tokens is None:
            beam_tokens = alternate_logprobs[:width]
        self.log.info("Next tokens: %s", beam_tokens)

        # 3. Go through each possible token for next position, create new beam for each.
        level_beams: list[LLMResponse] = []
        for token in beam_tokens[:width]:
            # 4. For each new beam, continue generating up to ``length`` tokens or until
            #    stopping criteria are met.
            beam = self._expand_beam(beam_prefix, token, length)
            if beam:
                level_beams.append(beam)
                if on_beam_completed:
                    on_beam_completed(beam)
            if on_check_stop and on_check_stop():
                self.log.info("Beam tree inference stopped by request.")
                break

        return level_beams

    def _find_beam_prefix(self, prefix: str) -> CompletionPrefix:
        """
        Locate a cached :class:`CompletionPrefix` for *prefix* or generate a new one
        when missing.
        """
        # Handle empty prefix case
        if not prefix:
            if self.zero_prefix:
                return self.zero_prefix
            return CompletionPrefix(prefix_text="", prefix_token_size=0, sampled_logprobs=CompletionTokenLogprobs([]))

        # Check cache first
        if prefix in self.cached_prefixes:
            return self.cached_prefixes[prefix]

        # First try to find in existing beams
        for beam in self.all_completions:
            beam_prefix = CompletionPrefix.try_get_from_response(prefix, beam)
            if beam_prefix:
                self.cached_prefixes[prefix] = beam_prefix
                return beam_prefix

        # Not found, need to generate it
        self.log.warning("Prefix not found in cache, evaluating it using the model: %s", prefix)
        prefix_completion = self.construct_completion_prefill(prefix)
        eval_logprobs = self.mapped_model.evaluate_completion(prompt=self.prompt_revision.prompt_text, completion=prefix_completion)
        beam_prefix = CompletionPrefix.create_from_eval(prefix, eval_logprobs)
        self.cached_prefixes[prefix] = beam_prefix
        return beam_prefix

    def fetch_next_token_logprobs_for_prefix(self, beam_prefix: CompletionPrefix | str, width: int) -> SinglePositionTopLogprobs:
        """
        Fetch logprobs for next token after given prefix, up to `width` top_k tokens.
        If not known, generate them using the provider.
        """
        if isinstance(beam_prefix, str) and beam_prefix == "" and self.zero_prefix:
            beam_prefix = self.zero_prefix  # Use cached empty prefix

        elif isinstance(beam_prefix, str):
            beam_prefix = self._find_beam_prefix(beam_prefix)

        # Check if we already have them
        # Make sure alternative_logprobs is longer than sampled_logprobs, so we have **NEXT** token alternative logprobs
        if (beam_prefix.alternative_logprobs and len(beam_prefix.alternative_logprobs) > len(beam_prefix.sampled_logprobs) and
                len(beam_prefix.alternative_logprobs[-1]) >= width):
            return beam_prefix.alternative_logprobs[-1]

        result = self.evaluate_beam_prefix(beam_prefix)
        if not result.alternative_logprobs or len(result.alternative_logprobs) == 0:
            raise ValueError("Provider did not return alternative logprobs as expected.")

        # Update the cached prefix with new logprobs
        beam_prefix.sampled_logprobs = result.sampled_logprobs
        beam_prefix.alternative_logprobs = result.alternative_logprobs
        return beam_prefix.alternative_logprobs[-1]

    def _expand_beam(self, beam_prefix: CompletionPrefix, token: SinglePositionToken, length: int) -> LLMResponse | None:
        """
        Expand a single beam from its prefix, generating up to `length` tokens or until stopping criteria.

        Returns a LLMResponse if completed, or None if not.
        """
        # Construct CompletionPrefill with tokens from prefix + selected token
        completion_prefill = CompletionPrefill.from_tokens(beam_prefix.sampled_logprobs, [token])
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": completion_prefill,
            "temperature": self.default_temperature,
            "top_k": self.default_top_k,
            "context_length": self.default_context_length,
            "max_tokens": length,
            "top_logprobs": 1,
        }
        response = self.mapped_model.generate(**generation_kwargs)

        self.reconstruct_logprobs_and_completion_text(response, CompletionTokenLogprobs(beam_prefix.sampled_logprobs + [token]),
                                                      beam_prefix.alternative_logprobs)

        response.beam_token = token.token_str
        self.add_cached_completion(response)
        return response

    def reconstruct_logprobs_and_completion_text(self, response: LLMResponse, prefix_sampled_logprobs: CompletionTokenLogprobs,
                                                 prefix_alternative_logprobs: CompletionTopLogprobs | None = None) -> None:
        """
        Reconstruct full logprobs and completion text for given response by prepending
        the provided prefix logprobs.

        Modifies the response in place.
        """
        sampled_logprobs = CompletionTokenLogprobs([])
        alternative_logprobs = CompletionTopLogprobs([])
        # Reconstruct full logprobs including prefix
        if response.logprobs and response.logprobs.sampled_logprobs:
            sampled_logprobs = CompletionTokenLogprobs.from_stitched_tokens(prefix_sampled_logprobs + response.logprobs.sampled_logprobs)
            completion_text = sampled_logprobs.build_full_text()
            if completion_text != response.completion_text:
                self.log.warning("Reconstructed completion text does not match response text, replacing it.")
                response.completion_text = completion_text  # Fix completion text if needed
        if response.logprobs and response.logprobs.alternative_logprobs and prefix_alternative_logprobs:
            alternative_logprobs = CompletionTopLogprobs(prefix_alternative_logprobs + response.logprobs.alternative_logprobs)

        logprobs = CommonCompletionLogprobs(
            logprobs_model_id=self.mapped_model.model_id,
            sampled_logprobs=sampled_logprobs,
            alternative_logprobs=alternative_logprobs,
        )

        response.logprobs = logprobs

    def generate_continuation(self, original_completion: CommonCompletionProtocol, context_length: int | None = None,
                              max_tokens: int | None = None) -> LLMResponse | None:
        """
        Generates continuation for given original completion.

        If mapped model and provider support high-fidelity continuation,
        then we use them to faithfully continue the original completion from the point it stopped.

        Otherwise, we re-generate the entire completion from previous prompt and prefill.

        Returns the new LLMResponse if successful, or None if continuation failed.
        """
        if self.provider.check_high_fidelity_continuation_possible(self.model_id, original_completion):
            return self.generate_high_fidelity_continuation(original_completion, context_length=context_length, max_tokens=max_tokens)

        if context_length is None:
            context_length = self.default_context_length

        if max_tokens is None:
            max_tokens = self.default_max_tokens

        self.log.warning("High-fidelity continuation not possible, re-generating full completion from previous prefill.")

        # When high-fidelity continuation is not possible, use the original completion text as prefill.
        prefill = self.construct_completion_prefill(original_completion)
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": prefill,
            "temperature": original_completion.temperature,
            "top_k": original_completion.top_k,
            "context_length": context_length,
            "max_tokens": max_tokens,
            "top_logprobs": 1,
        }
        response = self.mapped_model.generate(**generation_kwargs)
        self.all_completions.append(response)
        return response

    def generate_high_fidelity_continuation(self, original_completion: CommonCompletionProtocol, context_length: int | None = None,
                                            max_tokens: int | None = None) -> LLMResponse | None:
        """
        Generate high-fidelity continuation for given original completion.

        This requires that the mapped model and provider support high-fidelity continuation,
        and that the original completion contains full token logprobs.

        Returns the new LLMResponse if successful, or None if continuation failed.
        """
        self.log.info("Generating high-fidelity continuation for completion")
        logprobs = original_completion.get_logprobs_for_model_id(self.mapped_model.model_id)
        if not logprobs or not logprobs.sampled_logprobs:
            self.log.error("Original completion does not contain token logprobs for this model.")
            return None
        completion_prefill = CompletionPrefill.from_tokens(logprobs.sampled_logprobs)
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": completion_prefill,
            "temperature": original_completion.temperature,
            "top_k": original_completion.top_k,
            "context_length": context_length if context_length is not None else self.default_context_length,
            "max_tokens": max_tokens if max_tokens is not None else self.default_max_tokens,
            "top_logprobs": 1,
        }
        response = self.mapped_model.generate(**generation_kwargs)
        self.reconstruct_logprobs_and_completion_text(response, logprobs.sampled_logprobs, logprobs.alternative_logprobs)
        response.prefill = original_completion.prefill  # Keep original prefill text
        response.beam_token = original_completion.beam_token  # Keep original beam token if any
        self.add_cached_completion(response)
        return response

    def evaluate_completion_logprobs(self, completion: PromptCompletion, save: bool = False) -> CommonCompletionLogprobs:
        """
        Evaluate token logprobs for given completion using the mapped model and provider.

        Returns a CommonCompletionLogprobsProtocol object containing the logprobs.
        """
        completion_prefill = self.construct_completion_prefill(completion)
        eval_logprobs = self.mapped_model.evaluate_completion(prompt=completion.prompt_conversation, completion=completion_prefill,
                                                              context_length=max(self.default_context_length, completion.context_length))
        if save and self.dataset.session:
            PromptCompletionLogprobs.get_or_create_from_llm_response_logprobs(self.dataset, completion, self.mapped_model.model_id,
                                                                              eval_logprobs)
        return eval_logprobs

    def evaluate_beam_prefix(self, beam_prefix: CompletionPrefix) -> CommonCompletionLogprobs:
        """
        Evaluate token logprobs for given beam prefix using the mapped model and provider.

        Returns a CommonCompletionLogprobsProtocol object containing the logprobs.
        """
        completion_prefill = self.construct_completion_prefill(beam_prefix)
        eval_logprobs = self.mapped_model.evaluate_completion(
            prompt=self.prompt_revision.prompt_conversation, completion=completion_prefill,
            context_length=max(self.default_context_length, beam_prefix.prefix_token_size))
        return eval_logprobs

    def construct_completion_prefill(self, completion: PromptCompletion | CompletionPrefix | str | None) -> CompletionPrefill:
        """
        Construct a CompletionPrefill object from given PromptCompletion or raw text.

        Most important is to be faithful to original tokenization if tokenization data is available.
        """
        if completion is None:
            return CompletionPrefill(prefill_text="", prefill_tokenized=None)
        if isinstance(completion, str):
            # For now, simple solution. But actually we have to go through cache to see if this string was tokenized before.
            return CompletionPrefill(prefill_text=completion, prefill_tokenized=None)

        if isinstance(completion, CompletionPrefix):
            return CompletionPrefill(prefill_text=completion.prefix_text, prefill_tokenized=completion.sampled_logprobs)

        logprobs = completion.get_logprobs_for_model_id(self.mapped_model.model_id)
        if not logprobs or not logprobs.sampled_logprobs:
            # No tokenization data, return raw text
            self.log.info("No tokenization data available for completion, returning raw text prefill.")
            return CompletionPrefill(prefill_text=completion.completion_text, prefill_tokenized=None)
        return CompletionPrefill(prefill_text=completion.completion_text, prefill_tokenized=logprobs.sampled_logprobs)
