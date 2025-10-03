"""
Unit tests for WidgetSample completion sorting by rating and scored_logprob.
"""
import logging
import pytest
from unittest.mock import MagicMock

from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.facet import Facet
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.gui.widget_sample import WidgetSample
from py_fade.providers.llm_response import LLMResponse
from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs
from py_fade.data_formats.base_data_classes import SinglePositionToken

logger = logging.getLogger(__name__)


def create_completion_with_logprobs(dataset, prompt_revision, model_id, completion_text, scored_logprob_value):
    """
    Helper to create a completion with specific scored_logprob value.
    """
    # Create minimal logprobs that result in the desired scored_logprob
    # scored_logprob = min_logprob + avg_logprob * 2
    # Let's use: min_logprob = scored_logprob_value / 3, avg_logprob = scored_logprob_value / 3
    # This gives: scored_logprob = scored_logprob_value / 3 + (scored_logprob_value / 3) * 2 = scored_logprob_value
    target_logprob = scored_logprob_value / 3.0

    # Use the actual completion text as the token to avoid validation errors
    sampled_logprobs = CompletionTokenLogprobs([
        SinglePositionToken(token_id=0, token_str=completion_text, token_bytes=completion_text.encode('utf-8'),
                           logprob=target_logprob, span=1),
    ])
    alternative_logprobs = CompletionTopLogprobs([[]])

    response = LLMResponse(
        model_id=model_id,
        prompt_conversation=[],
        completion_text=completion_text,
        generated_part_text=completion_text,
        temperature=0.7,
        top_k=40,
        context_length=1024,
        max_tokens=128,
        logprobs=CommonCompletionLogprobs(
            logprobs_model_id=model_id,
            sampled_logprobs=sampled_logprobs,
            alternative_logprobs=alternative_logprobs,
        ),
    )

    _prompt_revision, completion = dataset.add_response_as_prompt_and_completion(
        prompt_revision.prompt_text,
        response,
    )
    return completion


class TestWidgetSampleSorting:
    """
    Test sorting of completions in WidgetSample by rating and scored_logprob.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        pass

    def test_sort_by_rating_only(self, app_with_dataset):
        """
        Test completions are sorted by rating when no logprobs available.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions without logprobs
        response1 = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Completion 1",
            generated_part_text="Completion 1",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )
        response2 = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Completion 2",
            generated_part_text="Completion 2",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )
        response3 = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Completion 3",
            generated_part_text="Completion 3",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )

        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        _pr2, completion2 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response2)
        _pr3, completion3 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response3)

        # Set ratings: completion2=5, completion1=3, completion3=no rating
        PromptCompletionRating.set_rating(dataset, completion2, facet, 5)
        PromptCompletionRating.set_rating(dataset, completion1, facet, 3)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet, None)

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Verify order: completion2 (rating=5), completion1 (rating=3), completion3 (rating=0)
        assert len(sorted_completions) == 3
        assert sorted_completions[0].completion_text == "Completion 2"
        assert sorted_completions[1].completion_text == "Completion 1"
        assert sorted_completions[2].completion_text == "Completion 3"

    def test_sort_by_logprob_within_same_rating(self,  app_with_dataset):
        """
        Test completions are sorted by scored_logprob within same rating group.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions with logprobs
        model_id = "test-model"
        completion1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Completion 1", -1.5)
        completion2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Completion 2", -0.5)
        completion3 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Completion 3", -2.0)

        # Set same rating for all
        PromptCompletionRating.set_rating(dataset, completion1, facet, 3)
        PromptCompletionRating.set_rating(dataset, completion2, facet, 3)
        PromptCompletionRating.set_rating(dataset, completion3, facet, 3)

        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget and set active model
        widget = WidgetSample(None, app_with_dataset, sample)
        

        # Mock mapped model
        mapped_model = MagicMock()
        mapped_model.model_id = model_id
        widget.set_active_context(facet, model_id)
        widget.active_model = mapped_model

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Verify order by scored_logprob (highest first): completion2 (-0.5), completion1 (-1.5), completion3 (-2.0)
        assert len(sorted_completions) == 3
        assert sorted_completions[0].completion_text == "Completion 2"
        assert sorted_completions[1].completion_text == "Completion 1"
        assert sorted_completions[2].completion_text == "Completion 3"

    def test_sort_completions_with_logprobs_before_without(self,  app_with_dataset):
        """
        Test completions with logprobs appear before those without logprobs within same rating group.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completion with logprobs
        model_id = "test-model"
        completion_with_logprobs = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "With logprobs", -1.5)

        # Create completion without logprobs
        response_without = LLMResponse(
            model_id=model_id,
            prompt_conversation=[],
            completion_text="Without logprobs",
            generated_part_text="Without logprobs",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )
        _pr, completion_without_logprobs = dataset.add_response_as_prompt_and_completion(sample.prompt_revision.prompt_text,
                                                                                         response_without)

        # Set same rating for both
        PromptCompletionRating.set_rating(dataset, completion_with_logprobs, facet, 3)
        PromptCompletionRating.set_rating(dataset, completion_without_logprobs, facet, 3)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget and set active model
        widget = WidgetSample(None, app_with_dataset, sample)
        

        # Mock mapped model
        mapped_model = MagicMock()
        mapped_model.model_id = model_id
        widget.set_active_context(facet, model_id)
        widget.active_model = mapped_model

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Verify order: completion with logprobs first
        assert len(sorted_completions) == 2
        assert sorted_completions[0].completion_text == "With logprobs"
        assert sorted_completions[1].completion_text == "Without logprobs"

    def test_sort_combined_rating_and_logprob(self,  app_with_dataset):
        """
        Test combined sorting by rating and scored_logprob.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        model_id = "test-model"
        # Create completions with different ratings and logprobs
        comp1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 5, logprob -1.0", -1.0)
        comp2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 5, logprob -2.0", -2.0)
        comp3 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 3, logprob -0.5", -0.5)
        comp4 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 3, logprob -1.5", -1.5)

        # Set ratings
        PromptCompletionRating.set_rating(dataset, comp1, facet, 5)
        PromptCompletionRating.set_rating(dataset, comp2, facet, 5)
        PromptCompletionRating.set_rating(dataset, comp3, facet, 3)
        PromptCompletionRating.set_rating(dataset, comp4, facet, 3)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget and set active model
        widget = WidgetSample(None, app_with_dataset, sample)
        

        # Mock mapped model
        mapped_model = MagicMock()
        mapped_model.model_id = model_id
        widget.set_active_context(facet, model_id)
        widget.active_model = mapped_model

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Expected order:
        # 1. Rating 5, logprob -1.0 (highest rating, best logprob in group)
        # 2. Rating 5, logprob -2.0 (highest rating, worse logprob in group)
        # 3. Rating 3, logprob -0.5 (lower rating, best logprob in group)
        # 4. Rating 3, logprob -1.5 (lower rating, worse logprob in group)
        assert len(sorted_completions) == 4
        assert sorted_completions[0].completion_text == "Rating 5, logprob -1.0"
        assert sorted_completions[1].completion_text == "Rating 5, logprob -2.0"
        assert sorted_completions[2].completion_text == "Rating 3, logprob -0.5"
        assert sorted_completions[3].completion_text == "Rating 3, logprob -1.5"

    def test_sort_no_active_facet(self,  app_with_dataset):
        """
        Test sorting when no active facet is set (all treated as rating=0).
        """
        dataset = app_with_dataset.current_dataset

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        model_id = "test-model"
        # Create completions with logprobs
        comp1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Logprob -1.5", -1.5)
        comp2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Logprob -0.5", -0.5)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget without active facet
        widget = WidgetSample(None, app_with_dataset, sample)
        

        # Mock mapped model
        mapped_model = MagicMock()
        mapped_model.model_id = model_id
        widget.set_active_context(None, model_id)
        widget.active_model = mapped_model

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Verify order by scored_logprob only (highest first): comp2 (-0.5), comp1 (-1.5)
        assert len(sorted_completions) == 2
        assert sorted_completions[0].completion_text == "Logprob -0.5"
        assert sorted_completions[1].completion_text == "Logprob -1.5"

    def test_sort_no_active_model(self,  app_with_dataset):
        """
        Test sorting when no active model is set (all logprobs ignored).
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        model_id = "test-model"
        # Create completions with logprobs
        comp1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 3", -1.5)
        comp2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Rating 5", -0.5)

        # Set ratings
        PromptCompletionRating.set_rating(dataset, comp1, facet, 3)
        PromptCompletionRating.set_rating(dataset, comp2, facet, 5)
        # Refresh sample to get updated completions
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)


        # Create widget without active model
        widget = WidgetSample(None, app_with_dataset, sample)
        
        widget.set_active_context(facet, None)

        # Get sorted completions
        completions_to_display = [c for c in sample.prompt_revision.completions if not c.is_archived]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions_to_display)

        # Verify order by rating only: comp2 (rating=5), comp1 (rating=3)
        assert len(sorted_completions) == 2
        assert sorted_completions[0].completion_text == "Rating 5"
        assert sorted_completions[1].completion_text == "Rating 3"
