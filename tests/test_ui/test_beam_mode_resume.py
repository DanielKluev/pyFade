"""
Unit tests for beam mode resume functionality.

Tests the resume button visibility and behavior for both transient and persisted completions.
"""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.widget_completion_beams import WidgetCompletionBeams
from tests.helpers.data_helpers import create_simple_llm_response, create_test_completion
from tests.helpers.ui_helpers import mock_three_way_editor

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

logger = logging.getLogger(__name__)


class TestBeamModeResumeButton:
    """
    Test resume button visibility for beam mode completions.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_resume_button_hidden_for_non_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test resume button is hidden for non-truncated transient beams.
        """
        # Create a non-truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Complete beam text")
        beam.is_truncated = False

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Resume button should exist but be hidden
        assert frame.resume_button is not None
        assert frame.resume_button.isHidden()

    def test_resume_button_shown_for_truncated_unsaved_beam(self, app_with_dataset):
        """
        Test resume button is shown for truncated transient beams.
        """
        # Create a truncated LLMResponse
        beam = create_simple_llm_response("test-model", "Truncated beam")
        beam.is_truncated = True

        # Create a completion frame in beam mode
        frame = CompletionFrame(app_with_dataset.current_dataset, beam, parent=None, display_mode="beam")

        # Resume button should be visible
        assert frame.resume_button is not None
        assert not frame.resume_button.isHidden()
        assert frame.resume_button.toolTip() == "Resume generation from this truncated completion."

    def test_resume_button_shown_for_truncated_saved_beam(self, temp_dataset):
        """
        Test resume button is shown for truncated saved beam completions.
        """
        session = temp_dataset.session
        assert session is not None

        # Create a sample and truncated completion
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 128)
        sample = Sample.create_if_unique(temp_dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
            session.add(sample)
            session.commit()

        completion = create_test_completion(session, prompt_revision, {"is_truncated": True, "completion_text": "Truncated completion"})
        session.refresh(completion)

        # Create a completion frame in beam mode with saved completion
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Resume button should be visible
        assert frame.resume_button is not None
        assert not frame.resume_button.isHidden()

    def test_resume_button_hidden_for_archived_beam(self, temp_dataset):
        """
        Test resume button is hidden for archived beam completions even if truncated.
        """
        session = temp_dataset.session
        assert session is not None

        # Create a sample and truncated + archived completion
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 128)
        sample = Sample.create_if_unique(temp_dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
            session.add(sample)
            session.commit()

        completion = create_test_completion(session, prompt_revision, {"is_truncated": True, "is_archived": True,
                                                                       "completion_text": "Archived truncated"})
        session.refresh(completion)

        # Create a completion frame in beam mode
        frame = CompletionFrame(temp_dataset, completion, parent=None, display_mode="beam")

        # Resume button should be hidden because it's archived
        assert frame.resume_button is not None
        assert frame.resume_button.isHidden()


class TestBeamModeResumeHandlers:
    """
    Test resume handlers in WidgetCompletionBeams.
    """

    @pytest.fixture(autouse=True)
    def _setup_font(self, ensure_google_icon_font):
        """Auto-use the ensure_google_icon_font fixture."""
        _ = ensure_google_icon_font

    def test_transient_beam_resume_updates_frame_with_continuation(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam generates continuation and updates the frame in place.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"

        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a truncated transient beam
        truncated_beam = create_simple_llm_response("test-model", "Truncated")
        truncated_beam.is_truncated = True
        truncated_beam.context_length = 1024
        truncated_beam.max_tokens = 128
        truncated_beam.prompt_revision = MagicMock()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)
        assert len(widget.beam_frames) == 1

        # Mock the text generation controller to return expanded completion
        expanded_beam = create_simple_llm_response("test-model", "Truncated expanded continuation")
        expanded_beam.is_truncated = False
        expanded_beam.context_length = 1024
        expanded_beam.max_tokens = 128

        mock_controller = MagicMock()
        mock_controller.generate_continuation.return_value = expanded_beam

        # Mock get_or_create_text_generation_controller
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Trigger resume
        widget.on_beam_resume_requested(truncated_beam)

        # Verify the continuation was generated
        mock_controller.generate_continuation.assert_called_once()

        # Verify the beam frame was updated with the expanded completion
        assert len(widget.beam_frames) == 1
        updated_beam, updated_frame = widget.beam_frames[0]
        assert updated_beam is expanded_beam
        assert updated_frame.completion is expanded_beam

    def test_transient_beam_resume_handles_generation_failure(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam handles generation failures gracefully.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"

        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a truncated transient beam
        truncated_beam = create_simple_llm_response("test-model", "Truncated")
        truncated_beam.is_truncated = True
        truncated_beam.context_length = 1024
        truncated_beam.max_tokens = 128
        truncated_beam.prompt_revision = MagicMock()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)

        # Mock the text generation controller to raise an error
        mock_controller = MagicMock()
        mock_controller.generate_continuation.side_effect = RuntimeError("Generation failed")

        # Mock get_or_create_text_generation_controller
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: mock_controller)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger resume
            widget.on_beam_resume_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert len(widget.beam_frames) == 1
        beam, _frame = widget.beam_frames[0]
        assert beam is truncated_beam

    def test_transient_beam_resume_handles_no_controller(self, app_with_dataset, monkeypatch):
        """
        Test that resuming a transient beam handles missing controller gracefully.
        """
        # Create widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"

        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", None, mapped_model)

        # Create a truncated transient beam
        truncated_beam = create_simple_llm_response("test-model", "Truncated")
        truncated_beam.is_truncated = True
        truncated_beam.context_length = 1024
        truncated_beam.max_tokens = 128
        truncated_beam.prompt_revision = MagicMock()

        # Add beam to widget
        widget.add_beam_frame(truncated_beam)

        # Mock get_or_create_text_generation_controller to return None
        monkeypatch.setattr(app_with_dataset, "get_or_create_text_generation_controller", lambda *args, **kwargs: None)

        # Mock QMessageBox to avoid dialog
        with patch("py_fade.gui.widget_completion_beams.QMessageBox.warning"):
            # Trigger resume
            widget.on_beam_resume_requested(truncated_beam)

        # Verify the beam frame was NOT modified
        assert len(widget.beam_frames) == 1
        beam, _frame = widget.beam_frames[0]
        assert beam is truncated_beam

    def test_persisted_beam_resume_opens_three_way_editor(self, app_with_dataset, temp_dataset, monkeypatch, qt_app):
        """
        Test that resuming a persisted beam opens the three-way editor.
        """
        session = temp_dataset.session
        assert session is not None

        # Create a sample and truncated completion
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 128)
        sample = Sample.create_if_unique(temp_dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
            session.add(sample)
            session.commit()

        completion = create_test_completion(session, prompt_revision, {"is_truncated": True, "completion_text": "Truncated completion"})
        session.refresh(completion)

        # Create widget with sample widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"

        sample_widget = MagicMock()
        sample_widget.active_facet = None

        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", sample_widget, mapped_model)

        # Track if ThreeWayCompletionEditorWindow is created
        editor_instances = mock_three_way_editor(monkeypatch)

        # Trigger resume for persisted completion
        widget.on_beam_resume_requested(completion)
        qt_app.processEvents()

        # Verify the editor was created
        assert len(editor_instances) == 1

    def test_persisted_beam_resume_refreshes_sample_widget_on_success(self, app_with_dataset, temp_dataset, monkeypatch, qt_app):
        """
        Test that resuming a persisted beam refreshes the sample widget when editor returns success.
        """
        session = temp_dataset.session
        assert session is not None

        # Create a sample and truncated completion
        prompt_revision = PromptRevision.get_or_create(temp_dataset, "Test prompt", 2048, 128)
        sample = Sample.create_if_unique(temp_dataset, "Test sample", prompt_revision, None)
        if sample is None:
            sample = Sample.from_prompt_revision(temp_dataset, prompt_revision)
            session.add(sample)
            session.commit()

        completion = create_test_completion(session, prompt_revision, {"is_truncated": True, "completion_text": "Truncated completion"})
        session.refresh(completion)

        # Create widget with sample widget
        mapped_model = MagicMock()
        mapped_model.model_id = "test-model"
        mapped_model.path = "test-model"

        sample_widget = MagicMock()
        sample_widget.active_facet = None

        widget = WidgetCompletionBeams(None, app_with_dataset, "Test prompt", sample_widget, mapped_model)

        # Mock the editor and simulate success (return 1)
        editor_instances = mock_three_way_editor(monkeypatch)
        from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow  # pylint: disable=import-outside-toplevel
        monkeypatch.setattr(ThreeWayCompletionEditorWindow, "exec", lambda self: 1)

        # Trigger resume for persisted completion
        widget.on_beam_resume_requested(completion)
        qt_app.processEvents()

        # Verify populate_outputs was called on sample widget
        sample_widget.populate_outputs.assert_called_once()
