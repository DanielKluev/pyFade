import pytest

from py_fade.providers.mock_provider import (
    MockLLMProvider,
    MockResponseGenerator,
    _COMMON_OPENERS,
)


def _logprob_signature(sequence):
    result = []
    for entry in sequence:
        top = tuple(entry.top_logprobs) if entry.top_logprobs else tuple()
        result.append((entry.token, entry.logprob, top))
    return result


def test_mock_generator_is_deterministic():
    prompt = "User: Please summarise the data pipeline." " Also outline edge cases."
    generator_a = MockResponseGenerator(prompt, prefill="", max_length=32, top_logprobs=4)
    generator_b = MockResponseGenerator(prompt, prefill="", max_length=32, top_logprobs=4)

    sequence_a = _logprob_signature(list(generator_a))
    sequence_b = _logprob_signature(list(generator_b))

    assert sequence_a == sequence_b


def test_mock_generator_prefill_boundary_split():
    generator = MockResponseGenerator(
        prompt_text="User: continue the word",
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
    provider = MockLLMProvider()

    response = provider.generate(
        model_id="mock-echo-model",
        prompt="User: please describe asynchronous IO interplay with event loops.",
        top_logprobs=4,
        max_tokens=40,
    )

    assert response.response_text
    assert any(response.response_text.startswith(opener) for opener in _COMMON_OPENERS)
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


def test_mock_provider_evaluate_completion_matches_completion():
    provider = MockLLMProvider()
    completion = "Sure, this is a tiny completion."

    logprobs = provider.evaluate_completion(
        model_id="mock-echo-model",
        prompt="User: write something tiny",
        completion=completion,
        top_logprobs=5,
    )

    reconstructed = "".join(entry.token for entry in logprobs)
    assert reconstructed == completion
    for entry in logprobs:
        if entry.top_logprobs:
            assert entry.top_logprobs[0][0] == entry.token
            assert entry.top_logprobs[0][1] == pytest.approx(entry.logprob)
