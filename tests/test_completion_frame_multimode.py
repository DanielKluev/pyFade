"""Tests for the multi-mode CompletionFrame functionality."""

import logging
import pytest
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.providers.llm_response import LLMResponse, LLMPTokenLogProbs
from py_fade.dataset.completion import PromptCompletion


def _build_sample_with_completion(dataset, **completion_overrides):
    """Create a persisted sample with a single completion for tests - copied from test_completion_rating_widget."""
    from py_fade.dataset.completion import PromptCompletion
    from py_fade.dataset.prompt import PromptRevision
    from py_fade.dataset.sample import Sample
    import hashlib
    
    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, "Once upon", 2048, 128)
    sample = Sample.create_if_unique(dataset, "Rating sample", prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion_text = "Once upon a midnight dreary, while I pondered, weak and weary."
    completion_defaults = {
        "prompt_revision": prompt_revision,
        "model_id": "mock-echo-model",
        "temperature": 0.8,
        "top_k": 50,
        "completion_text": completion_text,
        "context_length": 2048,
        "max_tokens": 128,
        "sha256": hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
    }
    completion_defaults.update(completion_overrides)

    completion = PromptCompletion(**completion_defaults)
    session.add(completion)
    session.commit()

    return sample, completion


def test_completion_frame_sample_mode_default(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """CompletionFrame defaults to sample mode and shows sample-specific UI."""
    _ = ensure_google_icon_font
    
    sample, completion = _build_sample_with_completion(temp_dataset)
    
    # Create CompletionFrame without specifying mode (should default to "sample")
    frame = CompletionFrame(temp_dataset, completion)
    
    assert frame.display_mode == "sample"
    assert hasattr(frame, 'rating_widget')
    assert frame.rating_widget is not None
    assert frame.edit_button is not None
    assert frame.save_button is None
    assert frame.pin_button is None
    
    # Header should be visible in sample mode
    assert frame.model_label.isVisible()


def test_completion_frame_beam_mode_ui_elements(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """CompletionFrame in beam mode shows beam-specific UI."""
    _ = ensure_google_icon_font
    
    # Create an LLMResponse for beam mode
    beam = LLMResponse(
        model_id="test-model",
        full_history=[{"role": "user", "content": "Test prompt"}],
        full_response_text="Test beam response",
        response_text="Test beam response",
        temperature=0.7,
        top_k=40,
        context_length=1024,
        max_tokens=100,
        min_logprob=-0.5,
    )
    
    # Create CompletionFrame in beam mode
    frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
    
    assert frame.display_mode == "beam"
    assert not hasattr(frame, 'rating_widget')
    assert frame.edit_button is None
    assert frame.save_button is not None
    assert frame.pin_button is not None
    assert frame.archive_button is not None
    
    # Header should be hidden for unsaved beam
    assert not frame.model_label.isVisible()
    
    # Archive button should be hidden for unsaved beam
    assert not frame.archive_button.isVisible()


def test_completion_frame_beam_mode_signals(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """CompletionFrame in beam mode emits appropriate signals."""
    _ = ensure_google_icon_font
    
    beam = LLMResponse(
        model_id="test-model",
        full_history=[{"role": "user", "content": "Test prompt"}],
        full_response_text="Test beam response",
        response_text="Test beam response",
        temperature=0.7,
        top_k=40,
        context_length=1024,
        max_tokens=100,
    )
    
    frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
    
    # Set up signal spies
    discard_spy = QSignalSpy(frame.discard_requested)
    save_spy = QSignalSpy(frame.save_requested)
    pin_spy = QSignalSpy(frame.pin_toggled)
    
    # Test discard button
    frame.discard_button.click()
    assert len(discard_spy) == 1
    assert discard_spy[0][0] is beam
    
    # Test save button
    frame.save_button.click()
    assert len(save_spy) == 1
    assert save_spy[0][0] is beam
    
    # Test pin button
    frame.pin_button.click()
    assert len(pin_spy) == 1
    assert pin_spy[0][0] is beam
    assert pin_spy[0][1] is True  # is_pinned = True


def test_completion_frame_sample_mode_signals(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """CompletionFrame in sample mode emits appropriate signals.""" 
    _ = ensure_google_icon_font
    
    sample, completion = _build_sample_with_completion(temp_dataset)
    
    frame = CompletionFrame(temp_dataset, completion)
    
    # Set up signal spies
    discard_spy = QSignalSpy(frame.discard_requested)
    edit_spy = QSignalSpy(frame.edit_requested)
    
    # Test discard button
    frame.discard_button.click()
    assert len(discard_spy) == 1
    # Should show confirmation dialog for persisted completion, but we're testing signal emission
    
    # Test edit button
    frame.edit_button.click()
    assert len(edit_spy) == 1
    assert edit_spy[0][0] is completion


def test_completion_frame_pin_state_visual_update(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """Pin state changes update the frame visual appearance."""
    _ = ensure_google_icon_font
    
    beam = LLMResponse(
        model_id="test-model",
        full_history=[{"role": "user", "content": "Test prompt"}],
        full_response_text="Test beam response",
        response_text="Test beam response",
        temperature=0.7,
        top_k=40,
        context_length=1024,
        max_tokens=100,
    )
    
    frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
    
    # Initially not pinned
    assert not frame.is_pinned
    assert frame.styleSheet() == ""
    
    # Pin the frame
    frame.pin_button.click()
    
    # Should now be pinned with visual changes
    assert frame.is_pinned
    assert "border: 2px solid #ff8c00" in frame.styleSheet()
    
    # Unpin the frame
    frame.pin_button.click()
    
    # Should be unpinned and return to default style
    assert not frame.is_pinned
    assert frame.styleSheet() == ""


def test_completion_frame_text_highlighting_beam_mode(
    app_with_dataset,
    temp_dataset,
    qt_app: QApplication,
    ensure_google_icon_font,
) -> None:
    """Text highlighting works for beam mode with prefill and beam_token."""
    _ = ensure_google_icon_font
    
    beam = LLMResponse(
        model_id="test-model",
        full_history=[{"role": "user", "content": "Test prompt"}],
        full_response_text="Prefilled text and then beam token continuation",
        response_text="and then beam token continuation",
        temperature=0.7,
        top_k=40,
        context_length=1024,
        max_tokens=100,
        prefill="Prefilled text",
        beam_token="beam token",
    )
    
    frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
    
    # Verify text is displayed correctly
    assert frame.text_edit.toPlainText() == beam.full_response_text
    
    # The highlighting is applied via QTextCharFormat - we can test that the text is set
    # Full highlighting testing would require more complex cursor manipulation tests


if __name__ == "__main__":
    pytest.main([__file__])