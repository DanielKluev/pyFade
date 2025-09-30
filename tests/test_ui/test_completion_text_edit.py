"""Comprehensive tests for the CompletionTextEdit widget with heatmap and highlighting functionality."""

# pylint: disable=protected-access,too-many-positional-arguments,too-many-lines

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Tuple

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent

from py_fade.data_formats.base_data_classes import CommonConversation, CommonMessage
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.components.widget_completion_text_editor import CompletionTextEdit
from py_fade.providers.llm_response import LLMResponse, SinglePositionTokenLogprobs, LLMResponseLogprobs
from py_fade.providers.providers_manager import MappedModel
from py_fade.providers.mock_provider import MockLLMProvider
from tests.helpers.data_helpers import create_test_completion

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase


def _build_sample_with_completion(
    dataset: "DatasetDatabase",
    **completion_overrides,
) -> Tuple[Sample, PromptCompletion]:
    """Create a persisted sample with a single completion for tests."""
    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, "Test prompt", 2048, 128)
    sample = Sample.create_if_unique(dataset, "Test sample", prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion_text = "This is a test completion response."
    completion_overrides_local = {
        "temperature": 0.7,
        "top_k": 40,
        "completion_text": completion_text,
        "sha256": hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
    }
    completion_overrides_local.update(completion_overrides)

    completion = create_test_completion(session, prompt_revision, completion_overrides_local)

    return sample, completion


def _create_test_llm_response(**overrides) -> LLMResponse:
    """Create a test LLMResponse for beam mode testing."""
    defaults = {
        "model_id": "test-beam-model",
        "prompt_conversation": CommonConversation([CommonMessage(role="user", content="Test prompt")]),
        "completion_text": "This is a beam response with some content",
        "generated_part_text": "This is a beam response with some content",
        "temperature": 0.0,
        "top_k": 1,
        "context_length": 1024,
        "max_tokens": 100,
        "prefill": None,
        "beam_token": None,
        "is_truncated": False,
    }

    # Handle logprobs conversion from list to LLMResponseLogprobs
    if "logprobs" in overrides and isinstance(overrides["logprobs"], list):
        logprobs_list = overrides["logprobs"]
        overrides["logprobs"] = LLMResponseLogprobs(logprobs_model_id=overrides.get("model_id", defaults["model_id"]),
                                                    logprobs=logprobs_list)

    defaults.update(overrides)
    return LLMResponse(**defaults)


class TestCompletionTextEditBasicFunctionality:
    """Test basic functionality of CompletionTextEdit widget."""

    def test_text_edit_initialization(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: QApplication,  # pylint: disable=unused-argument
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionTextEdit initializes correctly."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        text_edit = frame.text_edit

        assert isinstance(text_edit, CompletionTextEdit)
        assert text_edit.completion_frame == frame
        assert text_edit.isReadOnly()
        assert text_edit.hasMouseTracking()

    def test_set_completion_basic(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """set_completion method works correctly."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, completion_text="Test completion text")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        text_edit = frame.text_edit

        assert text_edit.toPlainText() == "Test completion text"
        assert text_edit._completion == completion
        assert not text_edit.is_heatmap_mode

    def test_set_completion_with_different_text(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """set_completion updates text when completion changes."""
        _ = ensure_google_icon_font
        _, completion1 = _build_sample_with_completion(temp_dataset, completion_text="First completion")
        _, completion2 = _build_sample_with_completion(temp_dataset, completion_text="Second completion")

        frame = CompletionFrame(temp_dataset, completion1, display_mode="sample")
        text_edit = frame.text_edit

        assert text_edit.toPlainText() == "First completion"

        # Change completion
        text_edit.set_completion(completion2)
        assert text_edit.toPlainText() == "Second completion"
        assert text_edit._completion == completion2


class TestCompletionTextEditPrefillHighlighting:
    """Test prefill highlighting functionality."""

    def test_prefill_highlighting_applied(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Prefill text is highlighted correctly."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Prefilled text and continuation", prefill="Prefilled text")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        assert text_edit.toPlainText() == "Prefilled text and continuation"
        assert not text_edit.is_heatmap_mode  # Should be in prefill highlighting mode

    def test_beam_token_highlighting_applied(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Beam token is highlighted correctly."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Start token continuation", beam_token="token")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        assert text_edit.toPlainText() == "Start token continuation"
        assert not text_edit.is_heatmap_mode

    def test_prefill_and_beam_token_highlighting(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Both prefill and beam token are highlighted when present."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Prefilled token and more content", prefill="Prefilled token", beam_token="token")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        assert text_edit.toPlainText() == "Prefilled token and more content"
        assert not text_edit.is_heatmap_mode


class TestCompletionTextEditHeatmapMode:
    """Test heatmap mode functionality."""

    def test_heatmap_mode_basic_toggle(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap mode can be toggled on and off."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Hello world",
                                         logprobs=[SinglePositionTokenLogprobs("Hello", -0.1),
                                                   SinglePositionTokenLogprobs(" world", -0.8)])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Set logprobs and enable heatmap mode
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)

        assert text_edit.is_heatmap_mode
        assert text_edit._logprobs == beam.logprobs

        # Disable heatmap mode
        text_edit.set_heatmap_mode(False)
        assert not text_edit.is_heatmap_mode

    def test_heatmap_mode_requires_logprobs(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap mode cannot be enabled without logprobs."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="No logprobs here")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Try to enable heatmap mode without logprobs
        text_edit.set_heatmap_mode(True)

        assert not text_edit.is_heatmap_mode

    def test_heatmap_cache_updates_correctly(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Token position cache is updated correctly for tooltips."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Hello world",
                                         logprobs=[SinglePositionTokenLogprobs("Hello", -0.1),
                                                   SinglePositionTokenLogprobs(" world", -0.8)])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Enable heatmap mode with logprobs
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        frame.show()
        qt_app.processEvents()

        # Check that cache is populated
        assert len(text_edit._token_positions_cache) > 0

        # Verify cache content
        cache = text_edit._token_positions_cache
        # First token should be "Hello" at position 0-5
        assert cache[0][0] == 0  # start position
        assert cache[0][1] == 5  # end position
        assert cache[0][2].token == "Hello"
        assert cache[0][2].logprob == -0.1

        # Second token should be " world" at position 5-11
        assert cache[1][0] == 5  # start position
        assert cache[1][1] == 11  # end position
        assert cache[1][2].token == " world"
        assert cache[1][2].logprob == -0.8

    def test_heatmap_token_mismatch_handling(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Heatmap handles token/text mismatches gracefully."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(
            completion_text="Hello world",
            logprobs=[
                SinglePositionTokenLogprobs("Hello", -0.1),
                SinglePositionTokenLogprobs("mismatch", -0.8),  # This token doesn't match
                SinglePositionTokenLogprobs(" world", -0.9)
            ])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Enable heatmap mode
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        frame.show()
        qt_app.processEvents()

        # Should still work but may have fewer cached positions
        assert len(text_edit._token_positions_cache) >= 1  # At least "Hello" should match


class TestCompletionTextEditMouseInteraction:
    """Test mouse interaction for tooltips in heatmap mode."""

    def test_mouse_move_shows_tooltip_in_heatmap_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Mouse move events show tooltips in heatmap mode."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Hello world",
                                         logprobs=[SinglePositionTokenLogprobs("Hello", -0.1),
                                                   SinglePositionTokenLogprobs(" world", -0.8)])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Enable heatmap mode
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        frame.show()
        qt_app.processEvents()

        # Simulate mouse move to first character (should be in "Hello" token)
        cursor = text_edit.textCursor()
        cursor.setPosition(2)  # Position in "Hello"

        # Create mock mouse event - position in the middle of "Hello"
        # Note: In real testing, QToolTip.showText would be called
        # This is more of a smoke test to ensure the method doesn't crash
        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(text_edit.rect().center()),  # Convert QPoint to QPointF
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier)

        # This should not crash
        text_edit.mouseMoveEvent(mock_event)

    def test_mouse_move_ignores_non_heatmap_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Mouse move events are ignored when not in heatmap mode."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Hello world")

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        # Not in heatmap mode
        assert not text_edit.is_heatmap_mode
        assert len(text_edit._token_positions_cache) == 0

        # Mouse move should not do anything special
        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(text_edit.rect().center()),  # Convert QPoint to QPointF
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier)

        # This should not crash and should be handled by parent
        text_edit.mouseMoveEvent(mock_event)


class TestCompletionTextEditEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_completion_text(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Empty completion text is handled correctly."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset, completion_text="")

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        text_edit = frame.text_edit

        assert text_edit.toPlainText() == ""
        assert text_edit._completion == completion

    def test_none_completion_handling(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionTextEdit handles None completion gracefully."""
        _ = ensure_google_icon_font
        _, completion = _build_sample_with_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        text_edit = frame.text_edit

        # Reset to None (simulating edge case)
        text_edit._completion = None
        text_edit._update_text_display()

        # Should not crash
        assert text_edit._completion is None

    def test_logprobs_without_completion(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """Setting logprobs without completion is handled."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(logprobs=[SinglePositionTokenLogprobs("test", -1.0)])

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit

        # Clear completion first
        text_edit._completion = None

        # Try to set logprobs
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)

        # Should not enable heatmap mode without completion
        assert not text_edit.is_heatmap_mode

    def test_very_long_text_performance(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionTextEdit handles long text efficiently."""
        _ = ensure_google_icon_font
        # Create a long completion text
        long_text = "This is a test sentence. " * 100  # 2500 characters

        beam = _create_test_llm_response(
            completion_text=long_text,
            logprobs=[SinglePositionTokenLogprobs("This", -0.1)] * 10  # Some logprobs
        )

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        text_edit = frame.text_edit
        frame.show()
        qt_app.processEvents()

        assert text_edit.toPlainText() == long_text

        # Enable heatmap mode should not crash
        text_edit.set_logprobs(beam.logprobs)
        text_edit.set_heatmap_mode(True)
        qt_app.processEvents()

        # Should work without major performance issues
        assert text_edit.is_heatmap_mode


class TestCompletionTextEditIntegrationWithCompletionFrame:
    """Test integration between CompletionTextEdit and CompletionFrame."""

    def test_frame_heatmap_button_controls_text_edit(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionFrame heatmap button controls CompletionTextEdit heatmap mode."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="Hello world",
                                         logprobs=[SinglePositionTokenLogprobs("Hello", -0.1),
                                                   SinglePositionTokenLogprobs(" world", -0.8)])
        beam.is_full_response_logprobs = True

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")

        # Set target model to enable heatmap
        mock_provider = MockLLMProvider()
        test_model = MappedModel("test-beam-model", mock_provider)
        frame.set_target_model(test_model)

        frame.show()
        qt_app.processEvents()

        text_edit = frame.text_edit

        # Initially not in heatmap mode
        assert not frame.is_heatmap_mode
        assert not text_edit.is_heatmap_mode

        # Click heatmap button
        frame.heatmap_button.click()
        qt_app.processEvents()

        # Both frame and text edit should be in heatmap mode
        assert frame.is_heatmap_mode
        assert text_edit.is_heatmap_mode

        # Click again to disable
        frame.heatmap_button.click()
        qt_app.processEvents()

        assert not frame.is_heatmap_mode
        assert not text_edit.is_heatmap_mode

    def test_text_edit_heatmap_mode_with_target_model_change(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """CompletionTextEdit heatmap mode responds to target model changes."""
        _ = ensure_google_icon_font
        beam = _create_test_llm_response(completion_text="test", logprobs=[SinglePositionTokenLogprobs("test", -1.0)])
        beam.is_full_response_logprobs = True

        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        text_edit = frame.text_edit

        # Initially no target model, heatmap button should be hidden
        assert not frame.heatmap_button.isVisible()

        # Set target model
        mock_provider = MockLLMProvider()
        test_model = MappedModel("test-beam-model", mock_provider)
        frame.set_target_model(test_model)
        qt_app.processEvents()

        # Now heatmap button should be visible
        assert frame.heatmap_button.isVisible()

        # Enable heatmap mode
        frame.heatmap_button.click()
        qt_app.processEvents()

        assert text_edit.is_heatmap_mode
        assert text_edit._logprobs is not None
