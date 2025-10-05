"""
Unit tests for WidgetCompletionBeams sorting by pinned status and scored_logprob.
"""

import logging
from unittest.mock import MagicMock

import pytest

from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.llm_response import LLMResponse
from py_fade.data_formats.base_data_classes import CommonCompletionLogprobs, CompletionTokenLogprobs, CompletionTopLogprobs
from py_fade.data_formats.base_data_classes import SinglePositionToken

logger = logging.getLogger(__name__)


def create_beam_with_logprobs(model_id, completion_text, scored_logprob_value):
    """
    Helper to create a beam (LLMResponse) with specific scored_logprob value.
    """
    # Create minimal logprobs that result in the desired scored_logprob
    # scored_logprob = min_logprob + avg_logprob * 2
    target_logprob = scored_logprob_value / 3.0

    # Use the actual completion text as the token to avoid validation errors
    sampled_logprobs = CompletionTokenLogprobs([
        SinglePositionToken(token_id=0, token_str=completion_text, token_bytes=completion_text.encode('utf-8'), logprob=target_logprob,
                            span=1),
    ])
    alternative_logprobs = CompletionTopLogprobs([[]])

    return LLMResponse(
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


class TestWidgetCompletionBeamsSorting:
    """
    Test sorting of beam frames in WidgetCompletionBeams by pinned status and scored_logprob.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_sort_by_scored_logprob_unpinned(self, app_with_dataset):
        """
        Test unpinned beams are sorted by scored_logprob (highest/best scores first).
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams with different logprobs
        beam1 = create_beam_with_logprobs("test-model", "Beam 1", -1.5)
        beam2 = create_beam_with_logprobs("test-model", "Beam 2", -0.5)
        beam3 = create_beam_with_logprobs("test-model", "Beam 3", -2.0)

        # Add beam frames manually
        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame3 = CompletionFrame(app_with_dataset.current_dataset, beam3, parent=widget, display_mode="beam")

        widget.beam_frames = [(beam1, frame1), (beam2, frame2), (beam3, frame3)]

        # Sort frames
        widget.sort_beam_frames()

        # Verify order: highest scored_logprob first (beam2 -0.5, beam1 -1.5, beam3 -2.0)
        sorted_beams = [beam for beam, _frame in widget.beam_frames]
        assert len(sorted_beams) == 3
        assert sorted_beams[0].completion_text == "Beam 2"
        assert sorted_beams[1].completion_text == "Beam 1"
        assert sorted_beams[2].completion_text == "Beam 3"

    def test_sort_pinned_before_unpinned(self, app_with_dataset):
        """
        Test pinned beams appear before unpinned beams.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams with different logprobs
        beam1 = create_beam_with_logprobs("test-model", "Unpinned beam 1", -1.5)
        beam2 = create_beam_with_logprobs("test-model", "Pinned beam", -2.0)
        beam3 = create_beam_with_logprobs("test-model", "Unpinned beam 2", -0.5)

        # Add beam frames manually
        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame3 = CompletionFrame(app_with_dataset.current_dataset, beam3, parent=widget, display_mode="beam")

        # Mark frame2 as pinned
        frame2.is_pinned = True

        widget.beam_frames = [(beam1, frame1), (beam2, frame2), (beam3, frame3)]

        # Sort frames
        widget.sort_beam_frames()

        # Verify order: pinned beam first, then unpinned sorted by logprob (highest first)
        sorted_beams = [beam for beam, _frame in widget.beam_frames]
        assert len(sorted_beams) == 3
        assert sorted_beams[0].completion_text == "Pinned beam"
        assert sorted_beams[1].completion_text == "Unpinned beam 2"
        assert sorted_beams[2].completion_text == "Unpinned beam 1"

    def test_sort_multiple_pinned_by_logprob(self, app_with_dataset):
        """
        Test multiple pinned beams are sorted by scored_logprob (highest/best scores first).
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams with different logprobs
        beam1 = create_beam_with_logprobs("test-model", "Pinned beam 1", -1.5)
        beam2 = create_beam_with_logprobs("test-model", "Pinned beam 2", -0.5)
        beam3 = create_beam_with_logprobs("test-model", "Unpinned beam", -2.0)

        # Add beam frames manually
        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame3 = CompletionFrame(app_with_dataset.current_dataset, beam3, parent=widget, display_mode="beam")

        # Mark frame1 and frame2 as pinned
        frame1.is_pinned = True
        frame2.is_pinned = True

        widget.beam_frames = [(beam1, frame1), (beam2, frame2), (beam3, frame3)]

        # Sort frames
        widget.sort_beam_frames()

        # Verify order: pinned beams first sorted by logprob (highest first), then unpinned
        # Pinned: beam2 (-0.5) before beam1 (-1.5)
        # Unpinned: beam3 (-2.0)
        sorted_beams = [beam for beam, _frame in widget.beam_frames]
        assert len(sorted_beams) == 3
        assert sorted_beams[0].completion_text == "Pinned beam 2"
        assert sorted_beams[1].completion_text == "Pinned beam 1"
        assert sorted_beams[2].completion_text == "Unpinned beam"

    def test_sort_beams_without_logprobs_at_end(self, app_with_dataset):
        """
        Test beams without logprobs appear at the end.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams: some with logprobs, some without
        beam_with_logprobs = create_beam_with_logprobs("test-model", "With logprobs", -1.5)
        beam_without_logprobs = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Without logprobs",
            generated_part_text="Without logprobs",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )

        # Add beam frames manually
        frame_with = CompletionFrame(app_with_dataset.current_dataset, beam_with_logprobs, parent=widget, display_mode="beam")
        frame_without = CompletionFrame(app_with_dataset.current_dataset, beam_without_logprobs, parent=widget, display_mode="beam")

        widget.beam_frames = [(beam_without_logprobs, frame_without), (beam_with_logprobs, frame_with)]

        # Sort frames
        widget.sort_beam_frames()

        # Verify order: beam with logprobs first
        sorted_beams = [beam for beam, _frame in widget.beam_frames]
        assert len(sorted_beams) == 2
        assert sorted_beams[0].completion_text == "With logprobs"
        assert sorted_beams[1].completion_text == "Without logprobs"

    def test_sort_pinned_without_logprobs_before_unpinned_with_logprobs(self, app_with_dataset):
        """
        Test pinned beams without logprobs still appear before unpinned beams with logprobs.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams
        pinned_beam_no_logprobs = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Pinned no logprobs",
            generated_part_text="Pinned no logprobs",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )
        unpinned_beam_with_logprobs = create_beam_with_logprobs("test-model", "Unpinned with logprobs", -1.5)

        # Add beam frames manually
        frame_pinned = CompletionFrame(app_with_dataset.current_dataset, pinned_beam_no_logprobs, parent=widget, display_mode="beam")
        frame_unpinned = CompletionFrame(app_with_dataset.current_dataset, unpinned_beam_with_logprobs, parent=widget, display_mode="beam")

        frame_pinned.is_pinned = True

        widget.beam_frames = [(unpinned_beam_with_logprobs, frame_unpinned), (pinned_beam_no_logprobs, frame_pinned)]

        # Sort frames
        widget.sort_beam_frames()

        # Verify order: pinned beam first even without logprobs
        sorted_beams = [beam for beam, _frame in widget.beam_frames]
        assert len(sorted_beams) == 2
        assert sorted_beams[0].completion_text == "Pinned no logprobs"
        assert sorted_beams[1].completion_text == "Unpinned with logprobs"

    def test_on_beam_pinned_triggers_resort(self, app_with_dataset):
        """
        Test that on_beam_pinned triggers re-sorting of frames.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams
        beam1 = create_beam_with_logprobs("test-model", "Beam 1", -1.5)
        beam2 = create_beam_with_logprobs("test-model", "Beam 2", -0.5)

        # Add beam frames manually
        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")

        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        # Initially, beams should be sorted by logprob (highest first)
        widget.sort_beam_frames()
        initial_order = [beam.completion_text for beam, _frame in widget.beam_frames]
        assert initial_order == ["Beam 2", "Beam 1"]

        # Pin beam1 (which has worse logprob)
        frame1.is_pinned = True
        widget.on_beam_pinned(beam1, True)

        # After pinning, beam1 should be first (because it's pinned), then beam2
        new_order = [beam.completion_text for beam, _frame in widget.beam_frames]
        assert new_order == ["Beam 1", "Beam 2"]

    def test_sort_combined_pinned_and_logprobs(self, app_with_dataset):
        """
        Test comprehensive sorting with multiple pinned and unpinned beams with various logprobs.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create beams with different states
        pinned_beam1 = create_beam_with_logprobs("test-model", "Pinned -2.0", -2.0)
        pinned_beam2 = create_beam_with_logprobs("test-model", "Pinned -1.0", -1.0)
        unpinned_beam1 = create_beam_with_logprobs("test-model", "Unpinned -0.5", -0.5)
        unpinned_beam2 = create_beam_with_logprobs("test-model", "Unpinned -3.0", -3.0)
        unpinned_beam_no_logprobs = LLMResponse(
            model_id="test-model",
            prompt_conversation=[],
            completion_text="Unpinned no logprobs",
            generated_part_text="Unpinned no logprobs",
            temperature=0.7,
            top_k=40,
            context_length=1024,
            max_tokens=128,
        )

        # Add beam frames manually
        frame_p1 = CompletionFrame(app_with_dataset.current_dataset, pinned_beam1, parent=widget, display_mode="beam")
        frame_p2 = CompletionFrame(app_with_dataset.current_dataset, pinned_beam2, parent=widget, display_mode="beam")
        frame_u1 = CompletionFrame(app_with_dataset.current_dataset, unpinned_beam1, parent=widget, display_mode="beam")
        frame_u2 = CompletionFrame(app_with_dataset.current_dataset, unpinned_beam2, parent=widget, display_mode="beam")
        frame_u_no = CompletionFrame(app_with_dataset.current_dataset, unpinned_beam_no_logprobs, parent=widget, display_mode="beam")

        frame_p1.is_pinned = True
        frame_p2.is_pinned = True

        widget.beam_frames = [
            (unpinned_beam1, frame_u1),
            (pinned_beam1, frame_p1),
            (unpinned_beam_no_logprobs, frame_u_no),
            (pinned_beam2, frame_p2),
            (unpinned_beam2, frame_u2),
        ]

        # Sort frames
        widget.sort_beam_frames()

        # Expected order:
        # 1. Pinned beams sorted by logprob (highest/best first): Pinned -1.0, Pinned -2.0
        # 2. Unpinned beams sorted by logprob (highest/best first): Unpinned -0.5, Unpinned -3.0
        # 3. Beams without logprobs: Unpinned no logprobs
        sorted_beams = [beam.completion_text for beam, _frame in widget.beam_frames]
        assert sorted_beams == [
            "Pinned -1.0",
            "Pinned -2.0",
            "Unpinned -0.5",
            "Unpinned -3.0",
            "Unpinned no logprobs",
        ]
