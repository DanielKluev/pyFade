"""
Test Mock Provider test module.
"""
import pytest

from py_fade.providers.mock_provider import (
    MockLLMProvider,
    MockResponseGenerator,
    _COMMON_OPENERS,
    _VOCAB_TOKEN_STRINGS,
)

from py_fade.providers.flat_prefix_template import apply_flat_prefix_template, parse_flat_prefix_string
from py_fade.data_formats.base_data_classes import CommonConversation


def _logprob_signature(sequence):
    """
    Extract signature from logprob sequence for test comparison.

    Creates a comparable representation of logprob data for deterministic testing.
    """
    result = []
    for entry in sequence:
        # SinglePositionToken has token_str and logprob, but no top_logprobs
        result.append((entry.token_str, entry.logprob))
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

    Checks that top logprobs are unique and correctly ordered.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("please describe asynchronous IO interplay with event loops.")
    token_candidates = 200
    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=token_candidates,
        max_tokens=40,
    )

    assert response.generated_part_text
    assert any(response.generated_part_text.startswith(opener) for opener in _COMMON_OPENERS)
    assert response.logprobs

    inspected = 0
    # Iterate over sampled tokens and alternative logprobs together
    for sampled_token, alternatives in zip(response.logprobs.sampled_logprobs, response.logprobs.alternative_logprobs):
        assert alternatives is not None
        assert len(alternatives) > 0
        # First alternative should be the sampled token with its logprob
        assert alternatives[0].token_str == sampled_token.token_str
        assert alternatives[0].logprob == pytest.approx(sampled_token.logprob)
        tokens = [t.token_str for t in alternatives]
        assert len(alternatives) == token_candidates
        assert len(tokens) == len(set(tokens))  # all token candidates **MUST** be unique
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
    conversation = parse_flat_prefix_string(prompt)
    prefill = "Sure, here's a quick overview: "

    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        prefill=prefill,
        max_tokens=6,
    )

    assert response.prefill == prefill
    assert response.prompt_conversation.as_list() == messages
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
    from py_fade.data_formats.base_data_classes import CompletionPrefill
    
    provider = MockLLMProvider()
    completion_text = "Sure, this is a tiny completion."
    completion = CompletionPrefill(prefill_text=completion_text, prefill_tokenized=None)

    logprobs = provider.evaluate_completion(
        model_id="mock-echo-model",
        prompt=CommonConversation.from_single_user("write something tiny"),
        completion=completion,
        top_logprobs=5,
    )

    reconstructed = "".join(entry.token_str for entry in logprobs.sampled_logprobs)
    assert reconstructed == completion_text
    for entry in logprobs.sampled_logprobs:
        # Mock provider doesn't include alternative logprobs
        assert entry.token_str is not None
        assert entry.logprob is not None


def test_mock_provider_first_position_sentence_starters():
    """
    Test that first position includes common sentence starters in top_logprobs.

    Verifies that the first token position includes vocabulary-fitted
    sentence starters as part of the top_logprobs alternatives.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("Continue this conversation")

    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=50,
        max_tokens=1,
    )

    assert response.logprobs
    assert len(response.logprobs.alternative_logprobs) >= 1
    first_token_alternatives = response.logprobs.alternative_logprobs[0]
    assert first_token_alternatives

    # Check that common openers are included in alternatives
    all_tokens = [t.token_str for t in first_token_alternatives]
    opener_found = any(opener in all_tokens for opener in _COMMON_OPENERS[:5])
    assert opener_found, f"Expected at least one common opener in {all_tokens}"


def test_mock_provider_large_top_logprobs_uniqueness():
    """
    Test that large top_logprobs requests generate all unique tokens.

    Verifies that when requesting a large number of top_logprobs,
    all tokens in the result are unique, meeting the depth requirement of 200 tokens.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("Generate a response")

    large_count = 300  # Test beyond the 200 requirement
    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=large_count,
        max_tokens=3,
    )

    assert response.logprobs
    for alternatives in response.logprobs.alternative_logprobs:
        assert alternatives is not None
        tokens = [t.token_str for t in alternatives]
        assert len(tokens) == large_count
        assert len(tokens) == len(set(tokens)), f"Found duplicate tokens in {tokens[:10]}..."


def test_mock_provider_prefill_overlap_handling():
    """
    Test that prefill overlap is handled correctly in token generation.

    Verifies that when a prefill overlaps with the beginning of the generated text,
    the overlapping portion is correctly skipped in the streaming tokens.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("Complete this phrase")

    # Test case where prefill might overlap with generated content
    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        prefill="Sure, I'll",
        max_tokens=10,
    )

    assert response.prefill == "Sure, I'll"
    assert response.completion_text.startswith("Sure, I'll")
    assert response.generated_part_text
    assert response.generated_part_text != response.prefill

    # Verify the full completion is prefill + generated part
    assert response.completion_text == response.prefill + response.generated_part_text


def test_mock_provider_vocabulary_token_usage():
    """
    Test that vocabulary tokens from GPT-2 encoding are used in top_logprobs.

    Verifies that the mock provider uses actual vocabulary tokens
    for more realistic top_logprobs generation.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("Test vocabulary usage")

    response = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=100,
        max_tokens=3,
    )

    assert response.logprobs
    vocab_tokens_found = 0

    for alternatives in response.logprobs.alternative_logprobs:
        assert alternatives is not None
        tokens = [t.token_str for t in alternatives]

        # Check if any vocabulary tokens are present
        for token in tokens:
            if token in _VOCAB_TOKEN_STRINGS:
                vocab_tokens_found += 1
                break

    # Should find vocabulary tokens in the results
    assert vocab_tokens_found > 0, "Expected to find vocabulary tokens in top_logprobs"


def test_mock_provider_deterministic_with_improvements():
    """
    Test that improved mock provider maintains deterministic behavior.

    Verifies that despite the improvements, the mock provider still
    produces deterministic outputs for the same inputs.
    """
    provider = MockLLMProvider()
    conversation = CommonConversation.from_single_user("Test determinism")

    # Generate the same request twice
    response1 = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=50,
        max_tokens=5,
    )

    response2 = provider.generate(
        model_id="mock-echo-model",
        prompt=conversation,
        top_logprobs=50,
        max_tokens=5,
    )

    # Should be identical
    assert response1.generated_part_text == response2.generated_part_text
    assert response1.completion_text == response2.completion_text

    # Logprobs should also be identical
    assert len(response1.logprobs.sampled_logprobs) == len(response2.logprobs.sampled_logprobs)
    for lp1, lp2 in zip(response1.logprobs.sampled_logprobs, response2.logprobs.sampled_logprobs):
        assert lp1.token_str == lp2.token_str
        assert lp1.logprob == pytest.approx(lp2.logprob)
    # Check alternative logprobs are also identical
    assert len(response1.logprobs.alternative_logprobs) == len(response2.logprobs.alternative_logprobs)
    for alt1, alt2 in zip(response1.logprobs.alternative_logprobs, response2.logprobs.alternative_logprobs):
        assert len(alt1) == len(alt2)
        for t1, t2 in zip(alt1, alt2):
            assert t1.token_str == t2.token_str
            assert t1.logprob == pytest.approx(t2.logprob)
