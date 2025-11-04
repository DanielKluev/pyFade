"""
Test completions filtering logic.

Tests for CompletionsFilter class ensuring proper filtering behavior across all filter types
and correct AND logic when multiple filters are active.
"""
from py_fade.dataset.completions_filter import CompletionsFilter
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from tests.helpers.data_helpers import create_test_sample, create_test_completion_with_params


class TestCompletionsFilterBasics:
    """Test basic CompletionsFilter functionality."""

    def test_filter_initialization(self):
        """
        Test that filter initializes with correct default state.

        By default, only hide_archived should be True (active).
        """
        filter_obj = CompletionsFilter()

        assert filter_obj.hide_archived is True  # Default active
        assert filter_obj.hide_other_models is False
        assert filter_obj.hide_other_families is False
        assert filter_obj.hide_rated is False
        assert filter_obj.hide_low_rated is False
        assert filter_obj.hide_unrated is False
        assert filter_obj.hide_full is False
        assert filter_obj.hide_truncated is False
        assert filter_obj.target_model_id is None

    def test_set_target_model_id(self):
        """Test setting target model ID for model-based filtering."""
        filter_obj = CompletionsFilter()

        filter_obj.set_target_model_id("gemma3:12b")
        assert filter_obj.target_model_id == "gemma3:12b"

        filter_obj.set_target_model_id(None)
        assert filter_obj.target_model_id is None

    def test_set_get_filter(self):
        """Test setting and getting individual filter states."""
        filter_obj = CompletionsFilter()

        filter_obj.set_filter('hide_other_models', True)
        assert filter_obj.get_filter('hide_other_models') is True

        filter_obj.set_filter('hide_other_models', False)
        assert filter_obj.get_filter('hide_other_models') is False

        # Test unknown filter name
        filter_obj.set_filter('unknown_filter', True)
        assert filter_obj.get_filter('unknown_filter') is False

    def test_to_dict(self):
        """Test exporting filter state to dictionary."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_other_models = True
        filter_obj.hide_truncated = True

        state = filter_obj.to_dict()

        assert state['hide_other_models'] is True
        assert state['hide_truncated'] is True
        assert state['hide_archived'] is True  # Default
        assert state['hide_rated'] is False

    def test_from_dict(self):
        """Test importing filter state from dictionary."""
        filter_obj = CompletionsFilter()

        state = {
            'hide_other_models': True,
            'hide_truncated': True,
            'hide_archived': False,
        }

        filter_obj.from_dict(state)

        assert filter_obj.hide_other_models is True
        assert filter_obj.hide_truncated is True
        assert filter_obj.hide_archived is False

    def test_extract_model_family(self):
        """Test model family extraction logic."""
        # pylint: disable=protected-access
        assert CompletionsFilter._extract_model_family("gemma3:12b-it-q4_K_M") == "gemma3"
        assert CompletionsFilter._extract_model_family("llama3:8b") == "llama3"
        assert CompletionsFilter._extract_model_family("qwen2.5:14b") == "qwen2.5"
        assert CompletionsFilter._extract_model_family("no-colon-model") == "no-colon-model"


class TestCompletionsFilterArchived:
    """Test archive filtering."""

    def test_hide_archived_default_active(self, temp_dataset):
        """
        Test that hide_archived filter works and is active by default.
        """
        filter_obj = CompletionsFilter()

        # Create sample with completions
        _, prompt = create_test_sample(temp_dataset)
        completion_archived = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model",
                                                                 completion_text="archived", sha256="a" * 64)
        completion_archived.is_archived = True
        completion_active = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="active",
                                                               sha256="b" * 64)
        completion_active.is_archived = False
        temp_dataset.commit()

        # Default: hide archived
        assert filter_obj.should_show_completion(completion_archived) is False
        assert filter_obj.should_show_completion(completion_active) is True

        # Show archived
        filter_obj.hide_archived = False
        assert filter_obj.should_show_completion(completion_archived) is True
        assert filter_obj.should_show_completion(completion_active) is True


class TestCompletionsFilterModels:
    """Test model-based filtering."""

    def test_hide_other_models_exact_match(self, temp_dataset):
        """
        Test filtering by exact model ID.
        """
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False  # Disable to focus on model filter
        filter_obj.hide_other_models = True
        filter_obj.set_target_model_id("gemma3:12b")

        _, prompt = create_test_sample(temp_dataset)
        completion_match = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:12b", completion_text="matching",
                                                              sha256="a" * 64)
        completion_no_match = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:8b", completion_text="not matching",
                                                                 sha256="b" * 64)
        temp_dataset.commit()

        assert filter_obj.should_show_completion(completion_match) is True
        assert filter_obj.should_show_completion(completion_no_match) is False

    def test_hide_other_families_same_family(self, temp_dataset):
        """
        Test filtering by model family - same family should pass.
        """
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_other_families = True
        filter_obj.set_target_model_id("gemma3:12b")

        _, prompt = create_test_sample(temp_dataset)
        completion_same_family = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:8b",
                                                                    completion_text="same family", sha256="a" * 64)
        completion_other_family = create_test_completion_with_params(temp_dataset, prompt, model_id="llama3:8b",
                                                                     completion_text="other family", sha256="b" * 64)
        temp_dataset.commit()

        assert filter_obj.should_show_completion(completion_same_family) is True
        assert filter_obj.should_show_completion(completion_other_family) is False

    def test_model_filters_combined(self, temp_dataset):
        """
        Test that exact model and family filters can work independently.
        """
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.set_target_model_id("gemma3:12b")

        _, prompt = create_test_sample(temp_dataset)
        exact_match = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:12b", completion_text="exact",
                                                         sha256="a" * 64)
        family_match = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:8b", completion_text="family",
                                                          sha256="b" * 64)
        no_match = create_test_completion_with_params(temp_dataset, prompt, model_id="llama3:8b", completion_text="neither",
                                                      sha256="c" * 64)
        temp_dataset.commit()

        # Only exact model filter
        filter_obj.hide_other_models = True
        filter_obj.hide_other_families = False
        assert filter_obj.should_show_completion(exact_match) is True
        assert filter_obj.should_show_completion(family_match) is False
        assert filter_obj.should_show_completion(no_match) is False

        # Only family filter
        filter_obj.hide_other_models = False
        filter_obj.hide_other_families = True
        assert filter_obj.should_show_completion(exact_match) is True
        assert filter_obj.should_show_completion(family_match) is True
        assert filter_obj.should_show_completion(no_match) is False


class TestCompletionsFilterTruncation:
    """Test truncation-based filtering."""

    def test_hide_truncated(self, temp_dataset):
        """Test filtering truncated completions."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_truncated = True

        _, prompt = create_test_sample(temp_dataset)
        truncated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="truncated",
                                                       sha256="a" * 64)
        truncated.is_truncated = True
        full = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="full", sha256="b" * 64)
        full.is_truncated = False
        temp_dataset.commit()

        assert filter_obj.should_show_completion(truncated) is False
        assert filter_obj.should_show_completion(full) is True

    def test_hide_full(self, temp_dataset):
        """Test filtering non-truncated completions."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_full = True

        _, prompt = create_test_sample(temp_dataset)
        truncated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="truncated",
                                                       sha256="a" * 64)
        truncated.is_truncated = True
        full = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="full", sha256="b" * 64)
        full.is_truncated = False
        temp_dataset.commit()

        assert filter_obj.should_show_completion(truncated) is True
        assert filter_obj.should_show_completion(full) is False


class TestCompletionsFilterRatings:
    """Test rating-based filtering."""

    def test_hide_rated(self, temp_dataset):
        """Test filtering completions with any rating."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_rated = True

        facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
        _, prompt = create_test_sample(temp_dataset)
        rated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="rated",
                                                   sha256="a" * 64)
        unrated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="unrated",
                                                     sha256="b" * 64)
        temp_dataset.commit()

        # Add rating
        PromptCompletionRating.set_rating(temp_dataset, rated, facet, 4)

        assert filter_obj.should_show_completion(rated, facet) is False
        assert filter_obj.should_show_completion(unrated, facet) is True

    def test_hide_unrated(self, temp_dataset):
        """Test filtering completions without rating."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_unrated = True

        facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
        _, prompt = create_test_sample(temp_dataset)
        rated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="rated",
                                                   sha256="a" * 64)
        unrated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="unrated",
                                                     sha256="b" * 64)
        temp_dataset.commit()

        # Add rating
        PromptCompletionRating.set_rating(temp_dataset, rated, facet, 4)

        assert filter_obj.should_show_completion(rated, facet) is True
        assert filter_obj.should_show_completion(unrated, facet) is False

    def test_hide_low_rated(self, temp_dataset):
        """Test filtering low-rated completions (rating < 3)."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_low_rated = True

        facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
        _, prompt = create_test_sample(temp_dataset)
        low_rated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="low",
                                                       sha256="a" * 64)
        high_rated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="high",
                                                        sha256="b" * 64)
        unrated = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="unrated",
                                                     sha256="c" * 64)
        temp_dataset.commit()

        # Add ratings
        PromptCompletionRating.set_rating(temp_dataset, low_rated, facet, 2)
        PromptCompletionRating.set_rating(temp_dataset, high_rated, facet, 4)

        assert filter_obj.should_show_completion(low_rated, facet) is False
        assert filter_obj.should_show_completion(high_rated, facet) is True
        assert filter_obj.should_show_completion(unrated, facet) is True  # Unrated should pass

    def test_rating_filters_without_facet(self, temp_dataset):
        """Test that rating filters are ignored when no facet is provided."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False
        filter_obj.hide_rated = True
        filter_obj.hide_unrated = True

        _, prompt = create_test_sample(temp_dataset)
        completion = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="test",
                                                        sha256="a" * 64)
        temp_dataset.commit()

        # Without facet, rating filters should not apply
        assert filter_obj.should_show_completion(completion, None) is True


class TestCompletionsFilterCombinations:
    """Test combinations of multiple filters (AND logic)."""

    def test_multiple_filters_and_logic(self, temp_dataset):
        """
        Test that multiple filters work with AND logic.

        A completion must pass ALL active filters to be shown.
        """
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = False  # Start with all shown
        filter_obj.set_target_model_id("gemma3:12b")

        facet = Facet.create(temp_dataset, "Test Facet", "Test description", min_rating=7)
        _, prompt = create_test_sample(temp_dataset)

        # Create completion that can be tested with multiple filters
        completion = create_test_completion_with_params(temp_dataset, prompt, model_id="gemma3:12b", completion_text="test",
                                                        sha256="a" * 64)
        completion.is_truncated = False
        temp_dataset.commit()
        PromptCompletionRating.set_rating(temp_dataset, completion, facet, 4)

        # Initially all shown
        assert filter_obj.should_show_completion(completion, facet) is True

        # Enable model filter - should still pass
        filter_obj.hide_other_models = True
        assert filter_obj.should_show_completion(completion, facet) is True

        # Enable truncation filter - should still pass (not truncated)
        filter_obj.hide_truncated = True
        assert filter_obj.should_show_completion(completion, facet) is True

        # Enable hide_full filter - should now FAIL (it's not truncated)
        filter_obj.hide_full = True
        assert filter_obj.should_show_completion(completion, facet) is False

    def test_filter_completions_list(self, temp_dataset):
        """Test filtering a list of completions."""
        filter_obj = CompletionsFilter()
        filter_obj.hide_archived = True

        _, prompt = create_test_sample(temp_dataset)
        active1 = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="active1",
                                                     sha256="a" * 64)
        active1.is_archived = False
        active2 = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="active2",
                                                     sha256="b" * 64)
        active2.is_archived = False
        archived = create_test_completion_with_params(temp_dataset, prompt, model_id="mock-echo-model", completion_text="archived",
                                                      sha256="c" * 64)
        archived.is_archived = True
        temp_dataset.commit()

        all_completions = [active1, active2, archived]
        filtered = filter_obj.filter_completions(all_completions)

        assert len(filtered) == 2
        assert active1 in filtered
        assert active2 in filtered
        assert archived not in filtered
