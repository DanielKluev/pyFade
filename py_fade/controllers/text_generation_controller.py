"""Controller logic for orchestrating text generation workflows."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from py_fade.data_formats.base_data_classes import CommonConversation, CommonCompletionLogprobsProtocol
from py_fade.dataset.prompt import PromptRevision
from py_fade.providers.llm_response import LLMResponseLogprobs, SinglePositionTokenLogprobs, LLMResponse
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
    logprobs: CommonCompletionLogprobsProtocol
    next_token_logprobs: list[tuple[str, float]] | None  # Top logprobs for next token after prefix, if known

    @classmethod
    def try_get_from_response(cls, prefix_text: str, response: LLMResponse) -> "CompletionPrefix|None":
        """
        Try to extract CompletionPrefix from LLMResponse if possible.
        Response must contain logprobs for all tokens in the prefix.
        """
        if not response.completion_text.startswith(prefix_text):
            return None  # Prefix does not match

        if not response.check_full_response_logprobs() or not response.logprobs:
            return None  # Logprobs do not cover full response

        prefix_tokens_count = 0
        current_pos = 0
        for lp in response.logprobs:
            if lp.token != prefix_text[current_pos:current_pos + len(lp.token)]:
                return None  # Token does not match prefix at this position
            current_pos += len(lp.token)
            prefix_tokens_count += 1
            if current_pos >= len(prefix_text):
                break

        if current_pos != len(prefix_text):
            return None  # Did not cover full prefix

        next_token_logprobs = None
        if len(response.logprobs.logprobs) > prefix_tokens_count:
            next_token_logprobs = response.logprobs.logprobs[prefix_tokens_count].top_logprobs

        # Successfully matched full prefix with logprobs, return slice of logprobs
        return cls(
            prefix_text=prefix_text,
            prefix_token_size=prefix_tokens_count,
            logprobs=response.logprobs[0:prefix_tokens_count],
            next_token_logprobs=next_token_logprobs,
        )

    @classmethod
    def create_from_eval(cls, prefix_text: str, eval_logprobs: CommonCompletionLogprobsProtocol) -> "CompletionPrefix":
        """
        Create CompletionPrefix from evaluated logprobs for given prefix text.
        """
        # Count tokens in prefix text
        prefix_tokens_count = len(eval_logprobs.logprobs)
        return cls(
            prefix_text=prefix_text,
            prefix_token_size=prefix_tokens_count,
            logprobs=eval_logprobs,
            next_token_logprobs=None,
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

    def __init__(self, app: "PyFadeApp", mapped_model: "MappedModel", dataset: "DatasetDatabase", prompt_revision: PromptRevision) -> None:
        """
        Bind the controller to the owning app, dataset, and selected model.
        """
        self.log = logging.getLogger("TextGenerationController")
        self.app = app
        self.all_completions = []
        self.cached_prefixes = {}
        self.default_temperature = app.config.default_temperature
        self.default_top_k = app.config.default_top_k
        self.default_context_length = app.config.default_context_length
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
            if completion.model_id != self.model_id:
                continue
            if not completion.check_full_response_logprobs():
                continue
            self.all_completions.append(completion)
        self.log.info(
            "Populated completions cache with %d existing completions from dataset.",
            len(self.all_completions),
        )

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
        self.all_completions.append(response)
        return response

    def beam_out_on_token_one_level(
        self,
        prefix: str,
        width: int,
        length: int,
        *,
        beam_tokens: list[tuple[str, float]] | None = None,
        on_beam_completed: Callable[[LLMResponse], None] | None = None,
        on_check_stop: Callable[[], bool] | None = None,
    ) -> list[LLMResponse]:
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
        if beam_tokens is None:
            beam_tokens = self.fetch_next_token_logprobs_for_prefix(beam_prefix, width)
        self.log.info("Next tokens: %s", beam_tokens)

        # 3. Go through each possible token for next position, create new beam for each.
        level_beams: list[LLMResponse] = []
        for token, logprob in beam_tokens[:width]:
            beam_token_prob = SinglePositionTokenLogprobs(token=token, logprob=logprob, top_logprobs=beam_tokens)
            # 4. For each new beam, continue generating up to ``length`` tokens or until
            #    stopping criteria are met.
            beam = self._expand_beam(beam_prefix, beam_token_prob, length)
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
            return CompletionPrefix(prefix_text="", prefix_token_size=0, logprobs=LLMResponseLogprobs(logprobs_model_id="", logprobs=[]),
                                    next_token_logprobs=None)

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
        eval_logprobs = self.mapped_model.evaluate_completion(prompt=self.prompt_revision.prompt_text, completion=prefix)
        beam_prefix = CompletionPrefix.create_from_eval(prefix, eval_logprobs)
        self.cached_prefixes[prefix] = beam_prefix
        return beam_prefix

    def fetch_next_token_logprobs_for_prefix(self, beam_prefix: CompletionPrefix | str, width: int) -> list[tuple[str, float]]:
        """
        Fetch logprobs for next token after given prefix, up to `width` top_k tokens.
        If not known, generate them using the provider.
        """
        if isinstance(beam_prefix, str):
            beam_prefix = self._find_beam_prefix(beam_prefix)
            # NOTE: Handle the case when prefix is empty by using any cached prefix with
            #       top_logprobs, avoiding reuse of the first token of another prefix.

        # Check if we already have them
        if beam_prefix.next_token_logprobs and len(beam_prefix.next_token_logprobs) >= width:
            return beam_prefix.next_token_logprobs

        # Need to generate them
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": beam_prefix.prefix_text,
            "temperature": self.default_temperature,
            "top_k": max(self.default_top_k, width),
            "context_length": self.default_context_length,
            "top_logprobs": width,
            "max_tokens": 1,
        }
        response = self.mapped_model.generate(**generation_kwargs)
        # Extract top_k logprobs from response
        if not response.logprobs:
            raise ValueError("Provider did not return token logprobs as expected.")

        next_token_logprobs = response.logprobs.first_token_top_logprobs
        return next_token_logprobs

    def _expand_beam(self, beam_prefix: CompletionPrefix, beam_token_prob: SinglePositionTokenLogprobs, length: int) -> LLMResponse | None:
        """
        Expand a single beam from its prefix, generating up to `length` tokens or until stopping criteria.
        Returns a LLMResponse if completed, or None if not.
        """
        prefill_text = beam_prefix.prefix_text + beam_token_prob.token
        generation_kwargs = {
            "prompt": self.prompt_conversation,
            "prefill": prefill_text,
            "temperature": self.default_temperature,
            "top_k": self.default_top_k,
            "context_length": self.default_context_length,
            "max_tokens": length,
            "top_logprobs": 1,
            "beam_token": beam_token_prob.token,
        }
        response = self.mapped_model.generate(**generation_kwargs)

        # Insert the beam token prob at the start of response logprobs
        logprobs = LLMResponseLogprobs.from_sequence(self.mapped_model.model_id, beam_prefix.logprobs, [beam_token_prob], response.logprobs)
        response.logprobs = logprobs
        self.all_completions.append(response)
        return response
