"""
Test Llama Cpp test module.
"""
# pylint: disable=protected-access
from __future__ import annotations

import logging

import pytest

import py_fade.providers.llama_cpp as llama_module
from py_fade.providers.llama_cpp import PrefillAwareLlamaCppInternal


def _make_provider() -> PrefillAwareLlamaCppInternal:
    provider = object.__new__(PrefillAwareLlamaCppInternal)
    provider.log = logging.getLogger("PrefillAwareLlamaCppInternalTest")
    provider.current_model_id = None  # Initialize missing attribute
    return provider


@pytest.mark.skipif(
    llama_module.is_llama_cpp_available,
    reason="llama_cpp is installed; the ImportError branch is not expected",
)
def test_prefill_provider_requires_llama_cpp_installation():
    """Test that PrefillAwareLlamaCppInternal raises ImportError when llama_cpp is not available."""
    with pytest.raises(ImportError):
        PrefillAwareLlamaCppInternal()


@pytest.mark.skip(reason="Method _convert_chat_completion_logprobs removed in new architecture")
def test_convert_chat_completion_logprobs_extracts_top_tokens():
    """Test that chat completion logprobs are properly converted to internal format."""
    # Method no longer exists in new architecture


@pytest.mark.skip(reason="Method _convert_simple_completion_logprobs removed in new architecture")
def test_convert_simple_completion_logprobs_handles_missing_top_entries():
    """Test that simple completion logprobs conversion handles missing top_logprobs entries gracefully."""
    # Method no longer exists in new architecture


@pytest.mark.skip(reason="Method mask_logprobs_by_str removed in new architecture")
def test_mask_logprobs_matches_completion_suffix():
    """Test that logprobs masking correctly matches completion text suffixes."""
    # Method no longer exists in new architecture
