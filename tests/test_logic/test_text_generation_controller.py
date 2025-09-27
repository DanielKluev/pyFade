"""
Test suite for TextGenerationController logic and operations.

Tests CompletionPrefix functionality and text generation workflow components.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from py_fade.controllers.text_generation_controller import CompletionPrefix, TextGenerationController
from py_fade.providers.llm_response import LLMResponse, LLMPTokenLogProbs

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def test_completion_prefix_creation():
    """Test CompletionPrefix creation and validation."""
    prefix_text = "Hello world"
    prefix_token_size = 2
    logprobs = [
        LLMPTokenLogProbs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1), ("Hi", -1.2)]),
        LLMPTokenLogProbs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5), (" there", -2.1)])
    ]
    
    prefix = CompletionPrefix(
        prefix_text=prefix_text,
        prefix_token_size=prefix_token_size,
        logprobs=logprobs
    )
    
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
        LLMPTokenLogProbs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1)]),
        LLMPTokenLogProbs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5)]),
        LLMPTokenLogProbs(token=" and", logprob=-0.8, top_logprobs=[(" and", -0.8)]),
        LLMPTokenLogProbs(token=" more", logprob=-1.2, top_logprobs=[(" more", -1.2)])
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
        LLMPTokenLogProbs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1)]),
        LLMPTokenLogProbs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5)])
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


def test_completion_prefix_create_from_eval():
    """Test CompletionPrefix creation from evaluation data."""
    eval_response = MagicMock(spec=LLMResponse)
    eval_response.response_text = "Hello world test"
    eval_response.logprobs = [
        LLMPTokenLogProbs(token="Hello", logprob=-0.1, top_logprobs=[("Hello", -0.1)]),
        LLMPTokenLogProbs(token=" world", logprob=-0.5, top_logprobs=[(" world", -0.5)]),
        LLMPTokenLogProbs(token=" test", logprob=-0.8, top_logprobs=[(" test", -0.8)])
    ]
    
    prefix = CompletionPrefix.create_from_eval("Hello", eval_response)
    
    assert prefix is not None
    assert prefix.prefix_text == "Hello"
    assert prefix.prefix_token_size == 1
    assert len(prefix.logprobs) == 1
    assert prefix.logprobs[0].token == "Hello"
    
    # Should have next token logprobs from the following token
    assert prefix.next_token_logprobs is not None
    assert prefix.next_token_logprobs == [(" world", -0.5)]


def test_text_generation_controller_initialization(temp_dataset: "DatasetDatabase"):
    """Test TextGenerationController initialization with required components."""
    # Create mock dependencies
    mock_app = MagicMock()
    mock_mapped_model = MagicMock()
    mock_prompt_revision = MagicMock()
    
    # Mock the MappedModel provider
    mock_mapped_model.provider = MagicMock()
    mock_mapped_model.id = "test-model"
    
    controller = TextGenerationController(
        app=mock_app,
        mapped_model=mock_mapped_model,
        prompt_revision=mock_prompt_revision,
        dataset=temp_dataset
    )
    
    assert controller.app is mock_app
    assert controller.mapped_model is mock_mapped_model
    assert controller.prompt_revision is mock_prompt_revision
    assert controller.dataset is temp_dataset
    assert controller.all_completions == []
    assert controller.cached_prefixes == {}


def test_controller_load_cache(temp_dataset: "DatasetDatabase"):
    """Test that controller can load cached prefix data."""
    mock_app = MagicMock()
    mock_mapped_model = MagicMock()
    mock_prompt_revision = MagicMock()
    mock_mapped_model.provider = MagicMock()
    
    controller = TextGenerationController(
        app=mock_app,
        mapped_model=mock_mapped_model,
        prompt_revision=mock_prompt_revision,
        dataset=temp_dataset
    )
    
    # Test that load_cache method exists and can be called
    assert hasattr(controller, 'load_cache')
    assert callable(controller.load_cache)
    
    # Load cache should not raise errors
    controller.load_cache()
    
    # Cached prefixes should be initialized as empty dict
    assert isinstance(controller.cached_prefixes, dict)