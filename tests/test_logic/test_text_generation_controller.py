"""
Test suite for TextGenerationController logic and operations.

Tests CompletionPrefix functionality and text generation workflow components.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from py_fade.controllers.text_generation_controller import CompletionPrefix
from py_fade.providers.llm_response import LLMResponse, SinglePositionTokenLogprobs

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_completion_prefix_creation():
    """Test CompletionPrefix creation and validation."""
    prefix_text = "Hello world"
    prefix_token_size = 2
    logprobs = [
        SinglePositionTokenLogprobs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1), ("Hi", -1.2)]),
        SinglePositionTokenLogprobs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5), (" there", -2.1)])
    ]

    prefix = CompletionPrefix(prefix_text=prefix_text, prefix_token_size=prefix_token_size, logprobs=logprobs)

    assert prefix.prefix_text == prefix_text
    assert prefix.prefix_token_size == prefix_token_size
    assert len(prefix.logprobs) == 2
    assert prefix.logprobs[0].token == "Hello"
    assert prefix.logprobs[1].token == " world"
    assert prefix.next_token_logprobs is None


def test_completion_prefix_from_response():
    """Test extracting CompletionPrefix from LLMResponse."""
    # Create a mock LLMResponse with proper logprobs
    response = MagicMock(spec=LLMResponse)
    response.full_response_text = "Hello world and more"
    response.check_full_response_logprobs.return_value = True
    response.logprobs = [
        SinglePositionTokenLogprobs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1)]),
        SinglePositionTokenLogprobs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5)]),
        SinglePositionTokenLogprobs(token=" and", logprob=-0.8, top_logprobs=[(" and", -0.8)]),
        SinglePositionTokenLogprobs(token=" more", logprob=-1.2, top_logprobs=[(" more", -1.2)])
    ]

    # Try to extract prefix "Hello world"
    prefix = CompletionPrefix.try_get_from_response("Hello world", response)

    assert prefix is not None
    assert prefix.prefix_text == "Hello world"
    assert len(prefix.logprobs) == 2
    assert prefix.logprobs[0].token == "Hello"
    assert prefix.logprobs[1].token == " world"


def test_completion_prefix_from_response_mismatch():
    """Test that CompletionPrefix extraction fails with mismatched prefix."""
    response = MagicMock(spec=LLMResponse)
    response.full_response_text = "Hello world"
    response.check_full_response_logprobs.return_value = True
    response.logprobs = [
        SinglePositionTokenLogprobs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1)]),
        SinglePositionTokenLogprobs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5)])
    ]

    # Try to extract a prefix that doesn't match
    prefix = CompletionPrefix.try_get_from_response("Hi there", response)

    assert prefix is None


def test_completion_prefix_from_response_no_logprobs():
    """Test that CompletionPrefix extraction fails without logprobs."""
    response = MagicMock(spec=LLMResponse)
    response.full_response_text = "Hello world"
    response.check_full_response_logprobs.return_value = False
    response.logprobs = None

    prefix = CompletionPrefix.try_get_from_response("Hello", response)

    assert prefix is None
