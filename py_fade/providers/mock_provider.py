"""Mock provider with deterministic GPT-2 tokenization simulation.

This module implements a mock LLM provider that mirrors several quirks of
``llama-cpp-python`` while remaining lightweight and perfectly deterministic.

Key behaviours implemented here:

* A greedy, merge-rule based GPT-2 tokenizer (via :mod:`tiktoken`) is used for
    both the "true" greedy tokenization of the full response and the simulated
    step-by-step streaming tokens.
* Generation is seeded from the combination of the prompt, prefill, and any
    forced response text so that results are reproducible across test runs.
* A preferred full response is pre-generated as if a greedy sampler (``t=0``
    and ``top_k=1``) had produced it. Each "true" token receives a base logprob,
    while the streamed tokens can split those true tokens to mimic mismatches
    between greedy tokenization and incremental decoding.
* Top-``k`` logprobs include the winning token plus deterministic noisy
    alternatives, keeping the primary token as the highest probability entry.
* The first user turn is extracted from the prompt; system and assistant turns
    are ignored deliberately so tests can focus on deterministic echoes.
* Generated completions open with common natural language openers such as
    ``"Sure,"`` or ``"Okay,"`` to better resemble real completions.
"""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Iterator, Sequence

import tiktoken

from py_fade.providers.base_provider import (
    BasePrefillAwareProvider,
    LOGPROB_LEVEL_TOP_LOGPROBS,
)
from py_fade.providers.llm_response import LLMResponse, LLMPTokenLogProbs


_GPT2_ENCODING = tiktoken.get_encoding("gpt2")
_COMMON_OPENERS: Sequence[str] = (
    "Sure,",
    "Okay,",
    "The",
    "Here",
    "Once",
    "In",
    "As",
    "When",
    "If",
    "To",
    "It",
    "I",
    "Given,",
)
_ALTERNATIVE_TOKENS: Sequence[str] = (
    "Absolutely",
    "Indeed",
    "Also",
    "However",
    "Therefore",
    "Moreover",
    "Additionally",
    "Consequently",
    "Furthermore",
    ".",
    ",",
    "?",
    "!",
    "the",
    "and",
    "to",
    "of",
    "for",
)


@dataclass(frozen=True)
class _TrueToken:
    text: str
    start: int
    end: int
    logprob: float
    generated_prefix: int


@dataclass(frozen=True)
class _StreamingTokenSpec:
    text: str
    logprob: float
    top_logprobs: list[tuple[str, float]] | None
    true_index: int


def _compute_seed(prompt_text: str, prefill: str, forced_response: str | None) -> int:
    hasher = hashlib.sha256()
    hasher.update(prompt_text.encode("utf-8", "replace"))
    hasher.update(b"<prefill>")
    hasher.update(prefill.encode("utf-8", "replace"))
    if forced_response is not None:
        hasher.update(b"<forced>")
        hasher.update(forced_response.encode("utf-8", "replace"))
    return int.from_bytes(hasher.digest()[:8], "big", signed=False)


def _canonicalize_messages(messages: Sequence[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")
        parts.append(f"{role}:{content.strip()}")
    return "\n".join(parts)


class MockResponseGenerator(Iterator[LLMPTokenLogProbs]):
    """Deterministic mock response generator used by :class:`MockLLMProvider`.

    The generator precomputes a greedy tokenization of the combined
    ``prefill + generated_text`` and then emits streaming tokens that may split
    those greedy tokens. This purposely creates situations where recomputing a
    greedy tokenization of the completed response produces a different token
    count compared to the streamed tokens, matching quirks observed in
    ``llama-cpp`` integrations.
    """

    def __init__(
        self,
        messages: Sequence[dict[str, str]],
        prefill: str,
        max_length: int,
        top_logprobs: int,
        forced_response_text: str | None = None,
    ) -> None:
        self.messages = [
            {
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
            }
            for message in messages
        ]
        self._prompt_signature = _canonicalize_messages(self.messages)
        self.prefill = prefill or ""
        self._forced_response_text = forced_response_text
        self.top_logprobs = max(0, int(top_logprobs))
        self._rng = random.Random(
            _compute_seed(self._prompt_signature, self.prefill, forced_response_text)
        )

        self.generated_text = (
            forced_response_text
            if forced_response_text is not None
            else self._build_preferred_response(self.messages)
        )
        if not self.generated_text:
            self.generated_text = (
                "Here's a placeholder completion from the deterministic mock provider."
            )

        self.full_text = self.prefill + self.generated_text
        self._true_tokens = self._compute_true_tokens()
        self._streaming_specs = self._build_streaming_specs()
        if not self._streaming_specs:
            fallback_token = _StreamingTokenSpec(
                text="",
                logprob=-1.0,
                top_logprobs=[("", -1.0)] if self.top_logprobs else None,
                true_index=0,
            )
            self._streaming_specs = [fallback_token]

        self.limit = max_length if max_length and max_length > 0 else None
        self._position = 0
        self.was_truncated = False

    def __iter__(self) -> "MockResponseGenerator":
        return self

    def __next__(self) -> LLMPTokenLogProbs:
        if self.limit is not None and self._position >= self.limit:
            if self._position < len(self._streaming_specs):
                self.was_truncated = True
            raise StopIteration
        if self._position >= len(self._streaming_specs):
            raise StopIteration

        spec = self._streaming_specs[self._position]
        self._position += 1
        top_logprobs = (
            list(spec.top_logprobs) if spec.top_logprobs is not None else None
        )
        return LLMPTokenLogProbs(token=spec.text, logprob=spec.logprob, top_logprobs=top_logprobs)

    @property
    def streaming_token_texts(self) -> list[str]:
        return [spec.text for spec in self._streaming_specs]

    @property
    def true_token_texts(self) -> list[str]:
        tokens = []
        for token in self._true_tokens:
            generated_text = token.text[token.generated_prefix :]
            if generated_text:
                tokens.append(generated_text)
        return tokens

    @property
    def has_more_tokens(self) -> bool:
        return self._position < len(self._streaming_specs)

    def full_generated_text(self, produced_only: bool = False) -> str:
        if produced_only:
            return "".join(self.streaming_token_texts[: self._position])
        return "".join(self.streaming_token_texts)

    def _build_preferred_response(self, messages: Sequence[dict[str, str]]) -> str:
        opener = self._rng.choice(_COMMON_OPENERS)
        user_turn = self._extract_primary_user_turn(messages)
        if not user_turn:
            body = (
                "this is a mocked completion so you can exercise the UI without a live model."
            )
            return f"{opener} {body}".strip()

        summary = " ".join(user_turn.split())
        if len(summary) > 220:
            summary = summary[:217].rstrip() + "..."
        body = (
            f"you mentioned {summary}. "
            "Here's a quick deterministic walkthrough that mirrors llama.cpp token streaming."
        )
        return f"{opener} {body}".strip()

    @staticmethod
    def _extract_primary_user_turn(messages: Sequence[dict[str, str]]) -> str:
        if not messages:
            return ""
        for message in messages:
            if message.get("role") == "user":
                content = message.get("content", "").strip()
                if content:
                    return content
        for message in messages:
            content = message.get("content", "").strip()
            if content:
                return content
        return ""

    def _compute_true_tokens(self) -> list[_TrueToken]:
        if not self.full_text:
            return []
        prefill_len = len(self.prefill)
        tokens: list[_TrueToken] = []
        offset = 0
        for token_id in _GPT2_ENCODING.encode(self.full_text):
            token_text = _GPT2_ENCODING.decode([token_id])
            start = offset
            end = start + len(token_text)
            offset = end
            if end <= prefill_len:
                continue
            generated_prefix = 0
            if start < prefill_len:
                generated_prefix = prefill_len - start
            logprob = self._sample_true_logprob(len(tokens))
            tokens.append(
                _TrueToken(
                    text=token_text,
                    start=start,
                    end=end,
                    logprob=logprob,
                    generated_prefix=generated_prefix,
                )
            )
        return tokens

    def _build_streaming_specs(self) -> list[_StreamingTokenSpec]:
        specs: list[_StreamingTokenSpec] = []
        for index, token in enumerate(self._true_tokens):
            generated_text = token.text[token.generated_prefix :]
            if not generated_text:
                continue
            forced_split = token.generated_prefix > 0
            pieces = self._split_token(generated_text, forced_split)
            for piece_index, piece in enumerate(pieces):
                logprob = token.logprob - (0.04 * piece_index)
                top = self._build_top_logprobs(piece, logprob)
                specs.append(
                    _StreamingTokenSpec(
                        text=piece,
                        logprob=logprob,
                        top_logprobs=top,
                        true_index=index,
                    )
                )
        return specs

    def _split_token(self, token_text: str, forced_split: bool) -> list[str]:
        if len(token_text) <= 1:
            return [token_text]
        max_pieces = min(3, len(token_text))
        pieces = 1
        if forced_split and max_pieces >= 2:
            pieces = 2
        else:
            roll = self._rng.random()
            if roll > 0.85 and max_pieces >= 3:
                pieces = 3
            elif roll > 0.55 and max_pieces >= 2:
                pieces = 2
        if pieces <= 1:
            return [token_text]
        pieces = min(pieces, len(token_text))
        cut_positions = sorted(self._rng.sample(range(1, len(token_text)), pieces - 1))
        segments: list[str] = []
        last_pos = 0
        for cut in cut_positions + [len(token_text)]:
            segments.append(token_text[last_pos:cut])
            last_pos = cut
        return segments

    def _build_top_logprobs(self, token: str, base_logprob: float) -> list[tuple[str, float]] | None:
        if self.top_logprobs <= 0:
            return None
        entries: list[tuple[str, float]] = [(token, base_logprob)]
        seen = {token}
        for rank in range(1, self.top_logprobs):
            candidate = self._choose_alternative_token(token, seen)
            seen.add(candidate)
            entries.append((candidate, base_logprob - 0.2 * rank))
        return entries

    def _choose_alternative_token(self, token: str, seen: set[str]) -> str:
        attempts = 0
        while attempts < 12:
            attempts += 1
            if token:
                index = self._rng.randrange(len(token))
                delta = 1 + (attempts % 3)
                candidate = list(token)
                candidate[index] = chr(((ord(candidate[index]) - 32 + delta) % 95) + 32)
                mutated = "".join(candidate)
            else:
                mutated = self._rng.choice(_ALTERNATIVE_TOKENS)
            mutated = mutated or self._rng.choice(_ALTERNATIVE_TOKENS)
            if mutated not in seen:
                return mutated
        for alternative in _ALTERNATIVE_TOKENS:
            if alternative not in seen:
                return alternative
        fallback = token + "-alt"
        return fallback

    def _sample_true_logprob(self, index: int) -> float:
        baseline = -0.45 - (0.05 * index)
        jitter = self._rng.uniform(-0.03, 0.03)
        return baseline + jitter


class MockLLMProvider(BasePrefillAwareProvider):
    """Mock implementation of an LLM provider.

    The provider generates deterministic completions that mimic llama.cpp-style
    token streaming. Only the first user turn from the prompt is considered; any
    preceding system messages or previous assistant turns are ignored on
    purpose, which keeps unit tests predictable.
    """

    logprob_capability = LOGPROB_LEVEL_TOP_LOGPROBS
    id: str = "mock"
    is_local_vram: bool = False

    def __init__(
        self,
        default_model_id: str = "mock-echo-model",
        default_temperature: float = 0.7,
        default_top_k: int = 40,
        default_context_length: int = 1024,
        default_max_tokens: int = 128,
    ) -> None:
        self.log = logging.getLogger("MockLLMProvider")
        super().__init__(
            default_temperature,
            default_top_k,
            default_context_length,
            default_max_tokens,
        )

    def generate(
        self,
        model_id: str,
        prompt: str,
        prefill: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        temperature = kwargs.get("temperature", self.default_temperature)
        top_k = kwargs.get("top_k", self.default_top_k)
        context_length = kwargs.get("context_length", self.default_context_length)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
        top_logprobs = kwargs.get("top_logprobs", 0)

        parsed_messages = self.flat_prefix_template_to_messages(prompt, prefill)
        history_messages: list[dict[str, str]] = []
        for index, message in enumerate(parsed_messages):
            role = message.get("role", "user")
            content = message.get("content", "")
            if (
                prefill
                and index == len(parsed_messages) - 1
                and role == "assistant"
                and content == prefill
            ):
                continue
            history_messages.append({"role": role, "content": content})

        generator = MockResponseGenerator(
            messages=history_messages,
            prefill=prefill or "",
            max_length=max_tokens,
            top_logprobs=top_logprobs,
        )

        response_tokens: list[str] = []
        logprobs: list[LLMPTokenLogProbs] = []
        for token_info in generator:
            response_tokens.append(token_info.token)
            logprobs.append(token_info)

        response_text = "".join(response_tokens)
        full_response_text = (prefill or "") + response_text
        is_truncated = generator.was_truncated or generator.has_more_tokens

        return LLMResponse(
            model_id=model_id,
            full_history=history_messages,
            full_response_text=full_response_text,
            response_text=response_text,
            temperature=temperature,
            top_k=top_k,
            prefill=prefill,
            context_length=context_length,
            max_tokens=max_tokens,
            logprobs=logprobs,
            is_truncated=is_truncated,
            beam_token=kwargs.get("beam_token", None),
        )

    def evaluate_completion(
        self,
        model_id: str,
        prompt: str,
        completion: str,
        **kwargs,
    ) -> list[LLMPTokenLogProbs]:
        top_logprobs = kwargs.get("top_logprobs", 20)
        parsed_messages = self.flat_prefix_template_to_messages(prompt)
        history_messages = [
            {"role": message.get("role", "user"), "content": message.get("content", "")}
            for message in parsed_messages
        ]
        generator = MockResponseGenerator(
            messages=history_messages,
            prefill="",
            max_length=0,
            top_logprobs=top_logprobs,
            forced_response_text=completion,
        )
        logprobs = list(generator)
        generated_text = "".join(lp.token for lp in logprobs)
        if generated_text != completion:
            self.log.debug(
                "Mock evaluate_completion trimmed completion mismatch: %s != %s",
                generated_text,
                completion,
            )
        return logprobs
