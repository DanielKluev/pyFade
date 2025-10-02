"""
Test suite for TextGenerationController logic and operations.

Tests CompletionPrefix functionality and text generation workflow components.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from py_fade.controllers.text_generation_controller import CompletionPrefix
from py_fade.providers.llm_response import LLMResponse
from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs
from tests.helpers.data_helpers import create_test_single_position_token

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_completion_prefix_creation():
    """Test CompletionPrefix creation and validation."""
    prefix_text = "Hello world"
    prefix_token_size = 2
    sampled_logprobs = CompletionTokenLogprobs(
        [create_test_single_position_token("Hello", -0.1),
         create_test_single_position_token(" world", -0.5)])

    prefix = CompletionPrefix(prefix_text=prefix_text, prefix_token_size=prefix_token_size, sampled_logprobs=sampled_logprobs,
                              alternative_logprobs=None)

    assert prefix.prefix_text == prefix_text
    assert prefix.prefix_token_size == prefix_token_size
    assert len(prefix.sampled_logprobs) == 2
    assert prefix.sampled_logprobs[0].token_str == "Hello"
    assert prefix.sampled_logprobs[1].token_str == " world"
    assert prefix.alternative_logprobs is None


def test_completion_prefix_from_response():
    """Test extracting CompletionPrefix from LLMResponse."""
    # Create a mock LLMResponse with proper logprobs
    response = MagicMock(spec=LLMResponse)
    response.completion_text = "Hello world and more"
    response.check_full_response_logprobs.return_value = True
    # Create proper CommonCompletionLogprobs object instead of old LLMResponseLogprobs
    sampled_logprobs = CompletionTokenLogprobs([
        create_test_single_position_token("Hello", -0.1),
        create_test_single_position_token(" world", -0.5),
        create_test_single_position_token(" and", -0.8),
        create_test_single_position_token(" more", -1.2)
    ])
    response.logprobs = CommonCompletionLogprobs(
        logprobs_model_id="test-model",
        sampled_logprobs=sampled_logprobs,
        alternative_logprobs=CompletionTopLogprobs(),
    )

    # Try to extract prefix "Hello world"
    prefix = CompletionPrefix.try_get_from_response("Hello world", response)

    assert prefix is not None
    assert prefix.prefix_text == "Hello world"
    assert len(prefix.sampled_logprobs) == 2
    assert prefix.sampled_logprobs[0].token_str == "Hello"
    assert prefix.sampled_logprobs[1].token_str == " world"


def test_completion_prefix_from_response_mismatch():
    """Test that CompletionPrefix extraction fails with mismatched prefix."""
    response = MagicMock(spec=LLMResponse)
    response.completion_text = "Hello world"
    response.check_full_response_logprobs.return_value = True
    # Create proper CommonCompletionLogprobs object
    sampled_logprobs = CompletionTokenLogprobs(
        [create_test_single_position_token("Hello", -0.1),
         create_test_single_position_token(" world", -0.5)])
    response.logprobs = CommonCompletionLogprobs(
        logprobs_model_id="test-model",
        sampled_logprobs=sampled_logprobs,
        alternative_logprobs=CompletionTopLogprobs(),
    )

    # Try to extract a prefix that doesn't match
    prefix = CompletionPrefix.try_get_from_response("Hi there", response)

    assert prefix is None


def test_completion_prefix_from_response_no_logprobs():
    """Test that CompletionPrefix extraction fails without logprobs."""
    response = MagicMock(spec=LLMResponse)
    response.completion_text = "Hello world"
    response.check_full_response_logprobs.return_value = False
    response.logprobs = None

    prefix = CompletionPrefix.try_get_from_response("Hello", response)

    assert prefix is None
