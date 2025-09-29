"""
Test Mock Provider test module.
"""
import pytest

from py_fade.providers.mock_provider import (
    MockLLMProvider,
    MockResponseGenerator,
    _COMMON_OPENERS,
)
from py_fade.providers.flat_prefix_template import apply_flat_prefix_template


def _logprob_signature(sequence):
    """
    Extract signature from logprob sequence for test comparison.

    Creates a comparable representation of logprob data for deterministic testing.
    """
    result = []
    for entry in sequence:
        top = tuple(entry.top_logprobs) if entry.top_logprobs else tuple()
        result.append((entry.token, entry.logprob, top))
    return result


def test_mock_generator_is_deterministic():
    """
    Test that mock generator produces deterministic outputs for same inputs.

    Verifies that the MockResponseGenerator produces identical outputs when
    given the same input parameters, ensuring test reproducibility.
    """
    messages = [{
        "role": "user",
        "content": "Please summarise the data pipeline. Also outline edge cases.",
    }]
    generator_a = MockResponseGenerator(messages, prefill="", max_length=32, top_logprobs=4)
    generator_b = MockResponseGenerator(messages, prefill="", max_length=32, top_logprobs=4)

    sequence_a = _logprob_signature(list(generator_a))
    sequence_b = _logprob_signature(list(generator_b))

    assert sequence_a == sequence_b


def test_mock_generator_prefill_boundary_split():
    """
    Test mock generator handles prefill boundary splitting correctly.

    Verifies that when a prefill ends in the middle of a token, the generator
    properly splits the token boundary for streaming behavior.
    """
    generator = MockResponseGenerator(
        messages=[{
            "role": "user",
            "content": "continue the word"
        }],
        prefill="Hel",
        max_length=0,
        top_logprobs=0,
        forced_response_text="lo world and beyond",
    )

    true_tokens = generator.true_token_texts
    streaming_tokens = generator.streaming_token_texts

    assert "".join(streaming_tokens) == generator.generated_text
    assert len(streaming_tokens) > len(true_tokens)
    assert streaming_tokens[:2] == ["l", "o"]
    assert "lo" in true_tokens


def test_mock_provider_generate_returns_top_logprobs():
    """
    Test mock provider returns top logprobs in generation response.

    Verifies that the mock provider properly generates logprob data
    matching the requested top_logprobs parameter.
    """
    provider = MockLLMProvider()

    response = provider.generate(
        model_id="mock-echo-model",
        prompt="please describe asynchronous IO interplay with event loops.",
        top_logprobs=4,
        max_tokens=40,
    )

    assert response.generated_part_text
    assert any(response.generated_part_text.startswith(opener) for opener in _COMMON_OPENERS)
    assert response.logprobs

    inspected = 0
    for entry in response.logprobs:
        if entry.top_logprobs:
            assert entry.top_logprobs[0][0] == entry.token
            assert entry.top_logprobs[0][1] == pytest.approx(entry.logprob)
            assert len(entry.top_logprobs) <= 4
            inspected += 1
        if inspected >= 3:
            break
    assert inspected >= 1


def test_mock_provider_generate_accepts_prefill_and_flat_prefix_prompt():
    """
    Test mock provider handles prefill and flat prefix prompt templates.

    Verifies that the provider correctly processes flat prefix template
    format and incorporates prefill text into the generation.
    """
    provider = MockLLMProvider()
    messages = [
        {
            "role": "system",
            "content": "You are a concise assistant."
        },
        {
            "role": "user",
            "content": "Continue the explanation about event loops."
        },
    ]
    prompt = apply_flat_prefix_template(messages)
    prefill = "Sure, here's a quick overview: "

    response = provider.generate(
        model_id="mock-echo-model",
        prompt=prompt,
        prefill=prefill,
        max_tokens=6,
    )

    assert response.prefill == prefill
    assert response.full_history == messages
    assert response.completion_text.startswith(prefill)
    assert response.generated_part_text
    assert response.generated_part_text != prefill
    assert response.completion_text == prefill + response.generated_part_text


def test_mock_provider_evaluate_completion_matches_completion():
    """
    Test mock provider evaluation matches the original completion.

    Verifies that when evaluating a completion, the mock provider returns
    logprobs that match the structure and content of the original completion.
    """
    provider = MockLLMProvider()
    completion = "Sure, this is a tiny completion."

    logprobs = provider.evaluate_completion(
        model_id="mock-echo-model",
        prompt="write something tiny",
        completion=completion,
        top_logprobs=5,
    )

    reconstructed = "".join(entry.token for entry in logprobs)
    assert reconstructed == completion
    for entry in logprobs:
        if entry.top_logprobs:
            assert entry.top_logprobs[0][0] == entry.token
            assert entry.top_logprobs[0][1] == pytest.approx(entry.logprob)
