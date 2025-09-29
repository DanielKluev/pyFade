"""
Test Llama Cpp test module.
"""
# pylint: disable=protected-access
from __future__ import annotations

import logging

import pytest

import py_fade.providers.llama_cpp as llama_module
from py_fade.providers.llama_cpp import PrefillAwareLlamaCppInternal
from py_fade.providers.llm_response import SinglePositionTokenLogprobs


def _make_provider() -> PrefillAwareLlamaCppInternal:
    provider = object.__new__(PrefillAwareLlamaCppInternal)
    provider.log = logging.getLogger("PrefillAwareLlamaCppInternalTest")
    return provider


@pytest.mark.skipif(
    llama_module.is_llama_cpp_available,
    reason="llama_cpp is installed; the ImportError branch is not expected",
)
def test_prefill_provider_requires_llama_cpp_installation():
    """Test that PrefillAwareLlamaCppInternal raises ImportError when llama_cpp is not available."""
    with pytest.raises(ImportError):
        PrefillAwareLlamaCppInternal()


def test_convert_chat_completion_logprobs_extracts_top_tokens():
    """Test that chat completion logprobs are properly converted to internal format."""
    provider = _make_provider()
    raw = {
        "content": [
            {
                "token": "Hello",
                "logprob": -0.1,
                "top_logprobs": [
                    {
                        "token": "Hello",
                        "logprob": -0.1
                    },
                    {
                        "token": "Hi",
                        "logprob": -1.5
                    },
                ],
            },
            {
                "token": "!",
                "logprob": -0.05,
                "top_logprobs": [{
                    "token": "!",
                    "logprob": -0.05
                }],
            },
        ]
    }

    converted = provider._convert_chat_completion_logprobs(raw)

    assert [lp.token for lp in converted] == ["Hello", "!"]
    assert converted[0].top_logprobs == [("Hello", -0.1), ("Hi", -1.5)]


def test_convert_simple_completion_logprobs_handles_missing_top_entries():
    """Test that simple completion logprobs conversion handles missing top_logprobs entries gracefully."""
    provider = _make_provider()
    raw = {
        "tokens": ["token", "trail"],
        "token_logprobs": [-0.3, -1.2],
        "top_logprobs": [{
            "token": -0.3
        }],
    }

    converted = provider._convert_simple_completion_logprobs(raw)

    assert [lp.token for lp in converted] == ["token", "trail"]
    assert converted[0].top_logprobs == [("token", -0.3)]
    assert converted[1].top_logprobs == []


def test_mask_logprobs_matches_completion_suffix():
    """Test that logprobs masking correctly matches completion text suffixes."""
    provider = _make_provider()
    logprobs = [
        SinglePositionTokenLogprobs(token="Sure", logprob=-0.1),
        SinglePositionTokenLogprobs(token=" ", logprob=-0.2),
        SinglePositionTokenLogprobs(token="thing", logprob=-0.3),
        SinglePositionTokenLogprobs(token="!", logprob=-0.4),
    ]

    matched = provider.mask_logprobs_by_str(logprobs, "Sure thing!", max_skip=1)

    assert matched is not None
    assert "".join(lp.token for lp in matched) == "Sure thing!"
