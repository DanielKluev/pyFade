"""
Unit tests for WidgetSample completion sorting by rating and scored_logprob.
"""
# pylint: disable=protected-access
import logging
from unittest.mock import MagicMock

import pytest

from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.facet import Facet
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.gui.widget_sample import WidgetSample
from tests.helpers.data_helpers import create_llm_response_with_logprobs, create_simple_llm_response

logger = logging.getLogger(__name__)


def create_completion_with_logprobs(dataset, prompt_revision, model_id, completion_text, scored_logprob_value):
    """
    Helper to create a completion with specific scored_logprob value.

    Wraps create_llm_response_with_logprobs and adds it to the dataset.
    """
    response = create_llm_response_with_logprobs(model_id, completion_text, scored_logprob_value)
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
        _ = ensure_google_icon_font

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
        response1 = create_simple_llm_response("test-model", "Completion 1")
        response2 = create_simple_llm_response("test-model", "Completion 2")
        response3 = create_simple_llm_response("test-model", "Completion 3")

        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        _pr2, completion2 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response2)
        _pr3, _completion3 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response3)

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

    def test_sort_by_logprob_within_same_rating(self, app_with_dataset):
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

    def test_sort_completions_with_logprobs_before_without(self, app_with_dataset):
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
        response_without = create_simple_llm_response(model_id, "Without logprobs")
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

    def test_sort_combined_rating_and_logprob(self, app_with_dataset):
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

    def test_sort_no_active_facet(self, app_with_dataset):
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
        _comp1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Logprob -1.5", -1.5)
        _comp2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model_id, "Logprob -0.5", -0.5)
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

    def test_sort_no_active_model(self, app_with_dataset):
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


class TestWidgetSampleDynamicSorting:
    """
    Test dynamic sorting of completion frames in WidgetSample.
    
    These tests verify that completion frames are re-sorted without recreating widgets
    when facet, model, rating, or logprobs change.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_sort_on_facet_change(self, app_with_dataset):
        """
        Test that completion frames are re-sorted when active facet changes.
        """
        dataset = app_with_dataset.current_dataset
        facet1 = Facet.create(dataset, "Facet1", "First test facet")
        facet2 = Facet.create(dataset, "Facet2", "Second test facet")

        # Create sample with completions
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions
        response1 = create_simple_llm_response("test-model", "Completion 1")
        response2 = create_simple_llm_response("test-model", "Completion 2")

        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        _pr2, completion2 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response2)

        # Set ratings for facet1: completion1=5, completion2=3
        PromptCompletionRating.set_rating(dataset, completion1, facet1, 5)
        PromptCompletionRating.set_rating(dataset, completion2, facet1, 3)

        # Set ratings for facet2: completion1=3, completion2=5 (opposite)
        PromptCompletionRating.set_rating(dataset, completion1, facet2, 3)
        PromptCompletionRating.set_rating(dataset, completion2, facet2, 5)

        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)

        # Create widget with facet1
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet1, None)

        # Verify initial order (facet1): completion1 first
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 1"
        assert widget.completion_frames[1][0].completion_text == "Completion 2"

        # Store references to the frames
        frame1 = widget.completion_frames[0][1]
        frame2 = widget.completion_frames[1][1]

        # Change to facet2
        widget.set_active_context(facet2, None)

        # Verify order changed (facet2): completion2 first
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 2"
        assert widget.completion_frames[1][0].completion_text == "Completion 1"

        # Verify frames were reused, not recreated
        assert widget.completion_frames[0][1] is frame2
        assert widget.completion_frames[1][1] is frame1

    def test_sort_on_model_change(self, app_with_dataset):
        """
        Test that completion frames are re-sorted when active model changes.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample with completions
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions - same rating, different logprobs for different models
        model1_id = "model1"
        model2_id = "model2"

        # Completion 1: better logprobs for model1, worse for model2
        completion1 = create_completion_with_logprobs(dataset, sample.prompt_revision, model1_id, "Completion 1", -1.0)
        # Create logprobs for model2 using a response
        response_comp1_model2 = create_llm_response_with_logprobs(model2_id, "Completion 1", -2.0)
        PromptCompletionLogprobs.get_or_create_from_llm_response_logprobs(dataset, completion1, model2_id, response_comp1_model2.logprobs)

        # Completion 2: worse logprobs for model1, better for model2
        completion2 = create_completion_with_logprobs(dataset, sample.prompt_revision, model1_id, "Completion 2", -2.0)
        response_comp2_model2 = create_llm_response_with_logprobs(model2_id, "Completion 2", -1.0)
        PromptCompletionLogprobs.get_or_create_from_llm_response_logprobs(dataset, completion2, model2_id, response_comp2_model2.logprobs)

        # Set same rating for both
        PromptCompletionRating.set_rating(dataset, completion1, facet, 5)
        PromptCompletionRating.set_rating(dataset, completion2, facet, 5)

        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)

        # Create widget with model1
        widget = WidgetSample(None, app_with_dataset, sample)
        mapped_model1 = MagicMock()
        mapped_model1.model_id = model1_id
        widget.set_active_context(facet, model1_id)
        widget.active_model = mapped_model1

        # Manually populate to get the frames
        widget.populate_outputs()

        # Verify initial order (model1): completion1 first (-1.0 > -2.0)
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 1"
        assert widget.completion_frames[1][0].completion_text == "Completion 2"

        # Store references to the frames
        frame1 = widget.completion_frames[0][1]
        frame2 = widget.completion_frames[1][1]

        # Change to model2
        mapped_model2 = MagicMock()
        mapped_model2.model_id = model2_id
        widget.set_active_context(facet, model2_id)
        widget.active_model = mapped_model2
        # Manually trigger sort since we're bypassing the normal model registration
        widget.sort_completion_frames()

        # Verify order changed (model2): completion2 first (-1.0 > -2.0)
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 2"
        assert widget.completion_frames[1][0].completion_text == "Completion 1"

        # Verify frames were reused, not recreated
        assert widget.completion_frames[0][1] is frame2
        assert widget.completion_frames[1][1] is frame1

    def test_sort_on_rating_change(self, app_with_dataset):
        """
        Test that completion frames are re-sorted when rating changes.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample with completions
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions
        response1 = create_simple_llm_response("test-model", "Completion 1")
        response2 = create_simple_llm_response("test-model", "Completion 2")

        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        _pr2, completion2 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response2)

        # Set initial ratings: completion1=5, completion2=3
        PromptCompletionRating.set_rating(dataset, completion1, facet, 5)
        PromptCompletionRating.set_rating(dataset, completion2, facet, 3)

        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)

        # Create widget
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet, None)

        # Verify initial order: completion1 first
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 1"
        assert widget.completion_frames[1][0].completion_text == "Completion 2"

        # Store references to the frames
        frame1 = widget.completion_frames[0][1]
        frame2 = widget.completion_frames[1][1]

        # Change rating: completion2 to 7 (higher than completion1's 5)
        PromptCompletionRating.set_rating(dataset, completion2, facet, 7)

        # Simulate rating change signal
        widget._on_rating_changed(7)

        # Verify order changed: completion2 first
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 2"
        assert widget.completion_frames[1][0].completion_text == "Completion 1"

        # Verify frames were reused, not recreated
        assert widget.completion_frames[0][1] is frame2
        assert widget.completion_frames[1][1] is frame1

    def test_sort_on_new_completion_added(self, app_with_dataset):
        """
        Test that completion frames are re-sorted when a new completion is added.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample with one completion
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create first completion with rating 3
        response1 = create_simple_llm_response("test-model", "Completion 1")
        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        PromptCompletionRating.set_rating(dataset, completion1, facet, 3)

        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)

        # Create widget
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet, None)

        # Verify initial state: one completion
        assert len(widget.completion_frames) == 1
        assert widget.completion_frames[0][0].completion_text == "Completion 1"

        # Add a new completion with higher rating
        response2 = create_llm_response_with_logprobs("test-model", "Completion 2", -1.0)
        widget.add_completion(response2)

        # Get the newly added completion and set its rating to 5 (higher than 3)
        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)
        completion2 = [c for c in sample.prompt_revision.completions if c.completion_text == "Completion 2"][0]
        PromptCompletionRating.set_rating(dataset, completion2, facet, 5)

        # Simulate the sort that should happen after rating
        widget.sort_completion_frames()

        # Verify order: completion2 first (rating 5), then completion1 (rating 3)
        assert len(widget.completion_frames) == 2
        assert widget.completion_frames[0][0].completion_text == "Completion 2"
        assert widget.completion_frames[1][0].completion_text == "Completion 1"

    def test_no_sort_when_nothing_changes(self, app_with_dataset):
        """
        Test that sort_completion_frames() is safe to call when nothing changes.
        """
        dataset = app_with_dataset.current_dataset
        facet = Facet.create(dataset, "TestFacet", "Test facet for sorting")

        # Create sample with completions
        prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
        sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(dataset, prompt_revision)
            dataset.session.add(sample)
            dataset.session.commit()

        # Create completions
        response1 = create_simple_llm_response("test-model", "Completion 1")
        response2 = create_simple_llm_response("test-model", "Completion 2")

        _pr1, completion1 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response1)
        _pr2, completion2 = dataset.add_response_as_prompt_and_completion(prompt_revision.prompt_text, response2)

        # Set ratings
        PromptCompletionRating.set_rating(dataset, completion1, facet, 5)
        PromptCompletionRating.set_rating(dataset, completion2, facet, 3)

        dataset.session.refresh(sample)
        dataset.session.refresh(sample.prompt_revision)

        # Create widget
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet, None)

        # Store initial order
        initial_order = [(c.completion_text, f) for c, f in widget.completion_frames]

        # Call sort multiple times
        widget.sort_completion_frames()
        widget.sort_completion_frames()
        widget.sort_completion_frames()

        # Verify order hasn't changed and frames are the same objects
        assert len(widget.completion_frames) == 2
        for i, (completion, frame) in enumerate(widget.completion_frames):
            assert completion.completion_text == initial_order[i][0]
            assert frame is initial_order[i][1]
