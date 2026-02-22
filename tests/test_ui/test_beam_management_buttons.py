"""
Unit tests for beam management buttons feature.

Tests cover:
1. Remove button on saved beam frames (removes from view without deleting from DB)
2. Pin button visibility for saved pinned beams (allows unpin)
3. Bulk action buttons on WidgetCompletionBeams top panel:
   - Unpin All
   - Remove Unpinned
   - Remove All
4. on_beam_remove_requested handler
5. unpin_all_beams handler
6. remove_all_unpinned_beams handler
7. remove_all_beams handler
"""

import logging

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from py_fade.gui.components.widget_completion import CompletionFrame
from tests.helpers.data_helpers import (create_llm_response_with_logprobs, create_simple_llm_response, build_sample_with_completion)
from tests.helpers.ui_helpers import create_mock_mapped_model

logger = logging.getLogger(__name__)


class TestRemoveButtonOnBeamFrames:
    """
    Test that saved beam frames have a remove button that removes from view without DB deletion.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_remove_button_exists_in_beam_mode(self, app_with_dataset):
        """
        Test that CompletionFrame in beam mode has a remove_button attribute.
        """
        beam = create_simple_llm_response("test-model", "Test beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, display_mode="beam")

        assert hasattr(frame, 'remove_button')
        assert frame.remove_button is not None

    def test_remove_button_hidden_for_unsaved_beam(self, app_with_dataset):
        """
        Test that remove_button is hidden for unsaved (transient) beams.
        """
        beam = create_simple_llm_response("test-model", "Unsaved beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, display_mode="beam")

        # Unsaved beams (LLMResponse without id) should not show remove button
        assert frame.remove_button is not None
        assert frame.remove_button.isHidden()

    def test_remove_button_visible_for_saved_beam(self, app_with_dataset):
        """
        Test that remove_button is visible for saved (persisted) beams.
        """
        # Create a saved completion
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)

        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="beam")

        # Saved beams should show remove button
        assert frame.remove_button is not None
        assert not frame.remove_button.isHidden()

    def test_remove_button_has_correct_tooltip(self, app_with_dataset):
        """
        Test that the remove button has a tooltip describing its action.
        """
        beam = create_simple_llm_response("test-model", "Test beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, display_mode="beam")

        assert frame.remove_button is not None
        assert "remove" in frame.remove_button.toolTip().lower() or "view" in frame.remove_button.toolTip().lower()
        assert "database" in frame.remove_button.toolTip().lower() or "delete" in frame.remove_button.toolTip().lower()

    def test_remove_button_emits_remove_requested_signal(self, app_with_dataset):
        """
        Test that clicking remove_button emits the remove_requested signal.
        """
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="beam")

        # Track signal emission
        signal_received = []
        frame.remove_requested.connect(signal_received.append)

        # Simulate remove button click
        frame.remove_button.click()

        assert len(signal_received) == 1
        assert signal_received[0] is saved_completion

    def test_remove_requested_signal_exists(self, app_with_dataset):
        """
        Test that CompletionFrame has the remove_requested signal.
        """
        beam = create_simple_llm_response("test-model", "Test beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, display_mode="beam")

        assert hasattr(frame, 'remove_requested')

    def test_remove_button_not_in_sample_mode(self, app_with_dataset):
        """
        Test that remove_button is None in sample mode (only beam mode has it).
        """
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="sample")

        # Sample mode should not have remove button
        assert frame.remove_button is None


class TestPinButtonVisibilityForSavedPinnedBeams:
    """
    Test that pin button is visible for saved pinned beams to allow unpinning.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_pin_button_visible_for_unsaved_unpinned_beam(self, app_with_dataset):
        """
        Test that pin button is visible for unsaved unpinned beams (can be pinned).
        """
        beam = create_simple_llm_response("test-model", "Unsaved beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, display_mode="beam")

        assert frame.pin_button is not None
        assert not frame.pin_button.isHidden()

    def test_pin_button_hidden_for_saved_unpinned_beam(self, app_with_dataset):
        """
        Test that pin button is hidden for saved unpinned beams (no need to pin/unpin).
        """
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="beam")

        # Not pinned, so pin_button should be hidden for saved beams
        assert frame.pin_button is not None
        assert frame.pin_button.isHidden()

    def test_pin_button_visible_for_saved_pinned_beam(self, app_with_dataset):
        """
        Test that pin button is visible for saved pinned beams (allows unpinning).
        """
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="beam")

        # Set as pinned
        frame.is_pinned = True
        frame._update_action_buttons()  # pylint: disable=protected-access

        # Pinned saved beam: pin_button should be visible to allow unpinning
        assert frame.pin_button is not None
        assert not frame.pin_button.isHidden()

    def test_pin_button_shows_unpin_tooltip_when_pinned_and_saved(self, app_with_dataset):
        """
        Test that pin button shows 'Unpin' tooltip when beam is pinned (saved or not).
        """
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, display_mode="beam")

        frame.is_pinned = True
        frame._update_action_buttons()  # pylint: disable=protected-access

        assert frame.pin_button is not None
        assert "unpin" in frame.pin_button.toolTip().lower()


class TestBulkActionButtons:
    """
    Test that WidgetCompletionBeams has bulk action buttons on the top panel.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_unpin_all_btn_exists(self, app_with_dataset):
        """
        Test that WidgetCompletionBeams has an unpin_all_btn button.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        assert hasattr(widget, 'unpin_all_btn')
        assert widget.unpin_all_btn is not None

    def test_remove_unpinned_btn_exists(self, app_with_dataset):
        """
        Test that WidgetCompletionBeams has a remove_unpinned_btn button.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        assert hasattr(widget, 'remove_unpinned_btn')
        assert widget.remove_unpinned_btn is not None

    def test_remove_all_btn_exists(self, app_with_dataset):
        """
        Test that WidgetCompletionBeams has a remove_all_btn button.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        assert hasattr(widget, 'remove_all_btn')
        assert widget.remove_all_btn is not None

    def test_unpin_all_btn_tooltip(self, app_with_dataset):
        """
        Test that the unpin all button has a descriptive tooltip.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        assert "unpin" in widget.unpin_all_btn.toolTip().lower()

    def test_remove_unpinned_btn_tooltip(self, app_with_dataset):
        """
        Test that the remove unpinned button has a descriptive tooltip mentioning no deletion.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        tooltip = widget.remove_unpinned_btn.toolTip().lower()
        assert "unpinned" in tooltip or "remove" in tooltip

    def test_remove_all_btn_tooltip(self, app_with_dataset):
        """
        Test that the remove all button has a descriptive tooltip mentioning no deletion.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        tooltip = widget.remove_all_btn.toolTip().lower()
        assert "remove" in tooltip or "all" in tooltip


class TestOnBeamRemoveRequested:
    """
    Test the on_beam_remove_requested handler removes beam from view without DB deletion.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_remove_requested_removes_beam_from_view(self, app_with_dataset):
        """
        Test that on_beam_remove_requested removes the beam frame from view.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Beam 2")
        widget.add_beam_frame(beam1)
        widget.add_beam_frame(beam2)

        assert len(widget.beam_frames) == 2

        # Trigger remove for beam1
        widget.on_beam_remove_requested(beam1)

        # beam1 should be removed, beam2 should remain
        assert len(widget.beam_frames) == 1
        remaining_beam, _ = widget.beam_frames[0]
        assert remaining_beam is beam2

    def test_remove_requested_does_not_delete_from_db(self, app_with_dataset):
        """
        Test that on_beam_remove_requested does not delete the completion from database.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a saved completion
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        saved_id = saved_completion.id

        # Add it as a beam frame (simulate saved beam in view)
        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, parent=widget.beams_container, display_mode="beam")
        frame.setFixedWidth(400)
        frame.setFixedHeight(300)
        frame.set_target_model(mapped_model)
        frame.discard_requested.connect(widget.on_beam_discarded)
        frame.remove_requested.connect(widget.on_beam_remove_requested)
        frame.save_requested.connect(widget.on_beam_accepted)
        frame.pin_toggled.connect(widget.on_beam_pinned)
        frame.resume_requested.connect(widget.on_beam_resume_requested)
        frame.limited_continuation_requested.connect(widget.on_beam_limited_continuation_requested)
        frame.beam_out_requested.connect(widget.on_beam_out_requested)
        frame.use_as_prefill_requested.connect(widget.on_use_as_prefill_requested)
        widget.beam_frames.append((saved_completion, frame))

        # Remove from view
        widget.on_beam_remove_requested(saved_completion)

        # Beam frame should be removed from view
        assert len(widget.beam_frames) == 0

        # But saved completion should still exist in database
        session = app_with_dataset.current_dataset.session
        db_completion = session.get(PromptCompletion, saved_id)
        assert db_completion is not None
        assert db_completion.id == saved_id

    def test_remove_requested_handles_unknown_completion(self, app_with_dataset):
        """
        Test that on_beam_remove_requested does nothing when completion is not found.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        widget.add_beam_frame(beam1)

        # Try to remove a beam that is not in the list
        unknown_beam = create_simple_llm_response("test-model", "Unknown beam")
        widget.on_beam_remove_requested(unknown_beam)

        # Nothing should change
        assert len(widget.beam_frames) == 1

    def test_remove_signal_connection_in_add_beam_frame(self, app_with_dataset):
        """
        Test that remove_requested signal is connected when adding a beam frame.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam = create_simple_llm_response("test-model", "Test beam")
        widget.add_beam_frame(beam)

        # The beam should be in the frames list
        assert len(widget.beam_frames) == 1
        _b, frame = widget.beam_frames[0]

        # Signal should be connected (we verify by triggering it)
        removed = []
        frame.remove_requested.connect(removed.append)
        frame.remove_requested.emit(beam)

        assert len(removed) == 1


class TestUnpinAllBeams:
    """
    Test the unpin_all_beams method.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_unpin_all_unpins_all_pinned_beams(self, app_with_dataset):
        """
        Test that unpin_all_beams unpins all pinned beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_llm_response_with_logprobs("test-model", "Pinned beam 1", -1.0)
        beam2 = create_llm_response_with_logprobs("test-model", "Pinned beam 2", -2.0)
        beam3 = create_llm_response_with_logprobs("test-model", "Unpinned beam", -3.0)

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame3 = CompletionFrame(app_with_dataset.current_dataset, beam3, parent=widget, display_mode="beam")

        frame1.is_pinned = True
        frame2.is_pinned = True
        # frame3 is not pinned

        widget.beam_frames = [(beam1, frame1), (beam2, frame2), (beam3, frame3)]

        widget.unpin_all_beams()

        # All beams should be unpinned
        assert not frame1.is_pinned
        assert not frame2.is_pinned
        assert not frame3.is_pinned

    def test_unpin_all_works_when_no_pinned_beams(self, app_with_dataset):
        """
        Test that unpin_all_beams works when there are no pinned beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Beam 2")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")

        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        # Should not raise any errors
        widget.unpin_all_beams()

        assert not frame1.is_pinned
        assert not frame2.is_pinned

    def test_unpin_all_works_with_empty_beams(self, app_with_dataset):
        """
        Test that unpin_all_beams works when there are no beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Should not raise any errors
        widget.unpin_all_beams()

        assert len(widget.beam_frames) == 0

    def test_unpin_all_triggers_resort(self, app_with_dataset):
        """
        Test that unpin_all_beams re-sorts frames after unpinning.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Beam with worse logprob but pinned
        beam1 = create_llm_response_with_logprobs("test-model", "Beam with worse logprob", -2.0)
        # Beam with better logprob but not pinned
        beam2 = create_llm_response_with_logprobs("test-model", "Beam with better logprob", -0.5)

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")

        frame1.is_pinned = True
        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        # Before unpin: beam1 (pinned) should be first
        widget.sort_beam_frames()
        assert widget.beam_frames[0][0].completion_text == "Beam with worse logprob"

        # After unpin all: beam2 (better logprob) should be first
        widget.unpin_all_beams()
        assert widget.beam_frames[0][0].completion_text == "Beam with better logprob"

    def test_unpin_all_btn_click(self, app_with_dataset):
        """
        Test that clicking unpin_all_btn calls unpin_all_beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam = create_simple_llm_response("test-model", "Test beam")
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=widget, display_mode="beam")
        frame.is_pinned = True
        widget.beam_frames = [(beam, frame)]

        # Click the unpin all button
        widget.unpin_all_btn.click()

        assert not frame.is_pinned


class TestRemoveAllUnpinnedBeams:
    """
    Test the remove_all_unpinned_beams method.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_remove_unpinned_removes_only_unpinned(self, app_with_dataset):
        """
        Test that remove_all_unpinned_beams removes only unpinned beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam_pinned = create_simple_llm_response("test-model", "Pinned beam")
        beam_unpinned1 = create_simple_llm_response("test-model", "Unpinned beam 1")
        beam_unpinned2 = create_simple_llm_response("test-model", "Unpinned beam 2")

        frame_pinned = CompletionFrame(app_with_dataset.current_dataset, beam_pinned, parent=widget, display_mode="beam")
        frame_unpinned1 = CompletionFrame(app_with_dataset.current_dataset, beam_unpinned1, parent=widget, display_mode="beam")
        frame_unpinned2 = CompletionFrame(app_with_dataset.current_dataset, beam_unpinned2, parent=widget, display_mode="beam")

        frame_pinned.is_pinned = True
        widget.beam_frames = [(beam_pinned, frame_pinned), (beam_unpinned1, frame_unpinned1), (beam_unpinned2, frame_unpinned2)]

        widget.remove_all_unpinned_beams()

        # Only pinned beam should remain
        assert len(widget.beam_frames) == 1
        remaining_beam, remaining_frame = widget.beam_frames[0]
        assert remaining_beam is beam_pinned
        assert remaining_frame is frame_pinned

    def test_remove_unpinned_with_all_pinned(self, app_with_dataset):
        """
        Test that remove_all_unpinned_beams keeps all beams when all are pinned.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Pinned beam 1")
        beam2 = create_simple_llm_response("test-model", "Pinned beam 2")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")

        frame1.is_pinned = True
        frame2.is_pinned = True
        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        widget.remove_all_unpinned_beams()

        # All beams should remain since all are pinned
        assert len(widget.beam_frames) == 2

    def test_remove_unpinned_with_no_pinned(self, app_with_dataset):
        """
        Test that remove_all_unpinned_beams removes all beams when none are pinned.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Beam 2")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")

        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        widget.remove_all_unpinned_beams()

        # All beams should be removed
        assert len(widget.beam_frames) == 0

    def test_remove_unpinned_does_not_delete_from_db(self, app_with_dataset):
        """
        Test that remove_all_unpinned_beams does not delete saved completions from database.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a saved completion
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        saved_id = saved_completion.id

        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, parent=widget.beams_container, display_mode="beam")
        widget.beam_frames.append((saved_completion, frame))
        # frame is not pinned

        widget.remove_all_unpinned_beams()

        # Beam frame should be removed from view
        assert len(widget.beam_frames) == 0

        # Saved completion should still be in database
        session = app_with_dataset.current_dataset.session
        db_completion = session.get(PromptCompletion, saved_id)
        assert db_completion is not None

    def test_remove_unpinned_btn_click(self, app_with_dataset):
        """
        Test that clicking remove_unpinned_btn calls remove_all_unpinned_beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Pinned beam")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame2.is_pinned = True

        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        widget.remove_unpinned_btn.click()

        # Only pinned beam should remain
        assert len(widget.beam_frames) == 1
        remaining_beam, _ = widget.beam_frames[0]
        assert remaining_beam is beam2


class TestRemoveAllBeams:
    """
    Test the remove_all_beams method.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_remove_all_removes_all_beams(self, app_with_dataset):
        """
        Test that remove_all_beams removes all beams from view.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Beam 2")
        beam3 = create_simple_llm_response("test-model", "Pinned beam")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame3 = CompletionFrame(app_with_dataset.current_dataset, beam3, parent=widget, display_mode="beam")
        frame3.is_pinned = True

        widget.beam_frames = [(beam1, frame1), (beam2, frame2), (beam3, frame3)]

        widget.remove_all_beams()

        # All beams should be removed including pinned ones
        assert len(widget.beam_frames) == 0

    def test_remove_all_works_with_empty_beams(self, app_with_dataset):
        """
        Test that remove_all_beams works when there are no beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Should not raise any errors
        widget.remove_all_beams()

        assert len(widget.beam_frames) == 0

    def test_remove_all_does_not_delete_from_db(self, app_with_dataset):
        """
        Test that remove_all_beams does not delete saved completions from database.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a saved completion
        _sample, saved_completion = build_sample_with_completion(app_with_dataset.current_dataset)
        saved_id = saved_completion.id

        frame = CompletionFrame(app_with_dataset.current_dataset, saved_completion, parent=widget.beams_container, display_mode="beam")
        frame.is_pinned = True
        widget.beam_frames.append((saved_completion, frame))

        widget.remove_all_beams()

        # Beam frame should be removed from view
        assert len(widget.beam_frames) == 0

        # Saved completion should still be in database
        session = app_with_dataset.current_dataset.session
        db_completion = session.get(PromptCompletion, saved_id)
        assert db_completion is not None

    def test_remove_all_btn_click(self, app_with_dataset):
        """
        Test that clicking remove_all_btn calls remove_all_beams.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Pinned beam")

        frame1 = CompletionFrame(app_with_dataset.current_dataset, beam1, parent=widget, display_mode="beam")
        frame2 = CompletionFrame(app_with_dataset.current_dataset, beam2, parent=widget, display_mode="beam")
        frame2.is_pinned = True

        widget.beam_frames = [(beam1, frame1), (beam2, frame2)]

        widget.remove_all_btn.click()

        # All beams should be removed
        assert len(widget.beam_frames) == 0

    def test_remove_all_clears_grid_layout(self, app_with_dataset):
        """
        Test that remove_all_beams clears the grid layout.
        """
        mapped_model = create_mock_mapped_model()
        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        beam1 = create_simple_llm_response("test-model", "Beam 1")
        beam2 = create_simple_llm_response("test-model", "Beam 2")
        widget.add_beam_frame(beam1)
        widget.add_beam_frame(beam2)

        assert widget.beams_layout.count() > 0

        widget.remove_all_beams()

        # Grid layout should be empty
        assert widget.beams_layout.count() == 0
        assert len(widget.beam_frames) == 0
