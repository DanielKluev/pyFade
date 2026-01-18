"""
Tests for get_min_logprob_token() method in CommonCompletionLogprobs.
"""
from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs
from tests.helpers.data_helpers import create_test_single_position_token


class TestGetMinLogprobToken:
    """
    Test get_min_logprob_token() method in CommonCompletionLogprobs class.

    This method should return the token with the minimum logprob value from the sampled tokens.
    """

    def test_get_min_logprob_token_single_token(self):
        """
        Test with a single token.

        Should return that token as it's the only one.
        """
        token = create_test_single_position_token("hello", -1.5)
        sampled_logprobs = CompletionTokenLogprobs([token])
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == "hello"
        assert min_token.logprob == -1.5

    def test_get_min_logprob_token_multiple_tokens(self):
        """
        Test with multiple tokens of different logprobs.

        Should return the token with the lowest logprob value.
        """
        tokens = [
            create_test_single_position_token("The", -0.5),
            create_test_single_position_token(" cat", -2.3),  # This has the lowest logprob
            create_test_single_position_token(" sat", -1.2),
            create_test_single_position_token(" down", -0.8),
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == " cat"
        assert min_token.logprob == -2.3

    def test_get_min_logprob_token_all_equal(self):
        """
        Test with all tokens having the same logprob.

        Should return the first token with that logprob value.
        """
        tokens = [
            create_test_single_position_token("All", -1.0),
            create_test_single_position_token(" same", -1.0),
            create_test_single_position_token(" value", -1.0),
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == "All"
        assert min_token.logprob == -1.0

    def test_get_min_logprob_token_empty_logprobs(self):
        """
        Test with empty sampled_logprobs.

        Should return None when there are no tokens.
        """
        sampled_logprobs = CompletionTokenLogprobs([])
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is None

    def test_get_min_logprob_token_with_positive_logprobs(self):
        """
        Test with positive logprob values (edge case).

        Should still correctly identify the minimum value.
        """
        tokens = [
            create_test_single_position_token("Token1", 0.5),
            create_test_single_position_token("Token2", 0.1),  # This is the minimum
            create_test_single_position_token("Token3", 0.8),
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == "Token2"
        assert min_token.logprob == 0.1

    def test_get_min_logprob_token_with_special_characters(self):
        """
        Test with tokens containing special characters.

        Should handle special characters correctly in token strings.
        """
        tokens = [
            create_test_single_position_token("Hello", -0.5),
            create_test_single_position_token("!", -3.2),  # Special character with lowest logprob
            create_test_single_position_token(" 🎉", -1.5),  # Emoji
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == "!"
        assert min_token.logprob == -3.2

    def test_get_min_logprob_token_with_very_negative_values(self):
        """
        Test with very negative logprob values.

        Should correctly identify the minimum even with extreme negative values.
        """
        tokens = [
            create_test_single_position_token("Normal", -1.0),
            create_test_single_position_token("Rare", -15.7),  # Very rare token
            create_test_single_position_token("Common", -0.2),
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.token_str == "Rare"
        assert min_token.logprob == -15.7

    def test_get_min_logprob_token_matches_min_logprob_value(self):
        """
        Test that the returned token's logprob matches the min_logprob value.

        The token returned by get_min_logprob_token() should have a logprob equal to min_logprob.
        """
        tokens = [
            create_test_single_position_token("First", -1.5),
            create_test_single_position_token("Second", -3.0),  # Minimum
            create_test_single_position_token("Third", -2.0),
        ]
        sampled_logprobs = CompletionTokenLogprobs(tokens)
        alternative_logprobs = CompletionTopLogprobs([])

        logprobs = CommonCompletionLogprobs("test-model", sampled_logprobs, alternative_logprobs)

        min_token = logprobs.get_min_logprob_token()

        assert min_token is not None
        assert min_token.logprob == logprobs.min_logprob
        assert logprobs.min_logprob == -3.0
