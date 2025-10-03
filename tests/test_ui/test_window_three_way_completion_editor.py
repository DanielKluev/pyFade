"""Integration tests for the three-way completion editor window."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_pairwise_ranks import PromptCompletionPairwiseRanking
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow, EditorMode

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase

_DEF_PROMPT = "What is the capital of France?"
_DEF_COMPLETION = "The capital of France is Paris."


def _persist_completion(
    dataset: "DatasetDatabase",
    *,
    model_id: str = "mock-echo-model",
    completion_text: str = _DEF_COMPLETION,
    max_tokens: int = 128,
    is_truncated: bool = False,
) -> PromptCompletion:
    """Create and commit a ``PromptCompletion`` attached to a prompt revision."""

    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, _DEF_PROMPT, 2048, max_tokens)

    completion = PromptCompletion(
        prompt_revision=prompt_revision,
        sha256=hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
        model_id=model_id,
        temperature=0.3,
        top_k=1,
        prefill=None,
        beam_token=None,
        completion_text=completion_text,
        tags=None,
        context_length=2048,
        max_tokens=max_tokens,
        is_truncated=is_truncated,
        is_archived=False,
    )
    session.add(completion)
    session.commit()
    session.refresh(completion)
    session.refresh(prompt_revision)
    return completion


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_manual_edit_saves_new_completion_with_pairwise_preference(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Saving a manual edit archives the parent and records a facet preference."""

    caplog.set_level(logging.DEBUG, logger="ThreeWayCompletionEditorWindow")

    original = _persist_completion(temp_dataset, completion_text=_DEF_COMPLETION)
    facet = Facet.create(temp_dataset, "Accuracy", "Overall factual correctness")
    temp_dataset.commit()

    window = ThreeWayCompletionEditorWindow(
        app_with_dataset,
        temp_dataset,
        original,
        EditorMode.MANUAL,
        facet=facet,
    )
    qt_app.processEvents()

    assert window.save_button is not None and not window.save_button.isEnabled()
    assert window.new_edit is not None

    window.new_edit.setPlainText(original.completion_text + "\nRewritten for clarity.")
    qt_app.processEvents()
    assert window.save_button.isEnabled()

    window.save_button.click()
    qt_app.processEvents()

    session = temp_dataset.session
    assert session is not None
    session.refresh(original)

    children = (session.query(PromptCompletion).filter(PromptCompletion.parent_completion_id == original.id).all())
    assert len(children) == 1

    new_completion = children[0]
    assert new_completion.model_id == "manual"
    assert new_completion.parent_completion_id == original.id
    assert new_completion.completion_text.endswith("Rewritten for clarity.")
    assert original.is_archived is True

    # Check that pairwise ranking was created (new API uses pairwise rankings instead of ratings)
    pairwise_ranking = PromptCompletionPairwiseRanking.get(temp_dataset, new_completion, original, facet)
    assert pairwise_ranking is not None

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_generation_role_persists_provider_metadata(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Continuing generation stores provider metadata and respects prefill text."""

    caplog.set_level(logging.DEBUG, logger="ThreeWayCompletionEditorWindow")

    original = _persist_completion(temp_dataset, model_id="mock-echo-model")

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # In continuation mode, generate button should be enabled if mapped model is available
    assert window.generate_button is not None and window.generate_button.isEnabled()
    window.generate_button.click()
    qt_app.processEvents()

    assert window.new_edit is not None
    generated_text = window.new_edit.toPlainText()
    assert generated_text.startswith(original.completion_text)

    assert window.save_button is not None and window.save_button.isEnabled()
    window.save_button.click()
    qt_app.processEvents()

    session = temp_dataset.session
    assert session is not None
    session.refresh(original)

    children = (session.query(PromptCompletion).filter(PromptCompletion.parent_completion_id == original.id).all())
    assert len(children) == 1

    continuation = children[0]
    assert continuation.model_id == "mock-echo-model"
    assert continuation.parent_completion_id == original.id
    assert continuation.prefill == original.completion_text
    assert continuation.is_archived is False

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_continuation_mode_window_title_shows_mapped_model(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> None:
    """Continuation mode window title shows the mapped model information."""

    original = _persist_completion(temp_dataset, model_id="mock-echo-model")

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # Window title should show the mapped model info
    assert "Continuation" in window.windowTitle()
    assert "mock-echo-model" in window.windowTitle()

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_continuation_mode_no_mapped_model_disables_generation(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> None:
    """Continuation mode with no mapped model disables generation button."""

    # Use a model ID that doesn't exist in the provider mapping
    original = _persist_completion(temp_dataset, model_id="nonexistent-model")

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # Window title should show no provider available
    assert "No provider for nonexistent-model" in window.windowTitle()

    # Generate button should be disabled
    assert window.generate_button is not None
    assert not window.generate_button.isEnabled()

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_continuation_mode_configures_token_parameters(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> None:
    """Continuation mode sets reasonable defaults for max tokens and context length."""

    # Create a truncated completion with low max tokens
    truncated_text = "The capital of France"  # Shorter than normal completion
    original = _persist_completion(temp_dataset, completion_text=truncated_text, max_tokens=50, is_truncated=True)

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # Check that max tokens and context length controls exist
    assert window.max_tokens_field is not None
    assert window.context_length_field is not None

    # Max tokens should be at least 1024 or 2 * original completion tokens
    max_tokens_value = window.max_tokens_field.value()
    assert max_tokens_value >= 1024

    # Context length should be set based on prompt + max tokens, rounded up to 1024 multiple
    context_length_value = window.context_length_field.value()
    assert context_length_value % 1024 == 0  # Should be multiple of 1024
    assert context_length_value > max_tokens_value  # Should include space for prompt

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_truncated_completion_continuation_workflow(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the complete workflow of continuing a truncated completion."""

    caplog.set_level(logging.DEBUG, logger="ThreeWayCompletionEditorWindow")

    # Create a truncated completion that should be continued
    truncated_text = "The capital of France"
    original = _persist_completion(temp_dataset, model_id="mock-echo-model", completion_text=truncated_text, max_tokens=32,
                                   is_truncated=True)

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # Verify UI state
    assert window.generate_button is not None and window.generate_button.isEnabled()
    assert window.max_tokens_field is not None
    assert window.context_length_field is not None

    # Check that max tokens is set to a reasonable value for continuation
    max_tokens_before = window.max_tokens_field.value()
    assert max_tokens_before >= 1024  # Should be at least 1024

    # Generate continuation
    window.generate_button.click()
    qt_app.processEvents()

    # Check that the new text is longer than the original (continuation worked)
    assert window.new_edit is not None
    continued_text = window.new_edit.toPlainText()
    assert len(continued_text) > len(truncated_text)
    assert continued_text.startswith(truncated_text)  # Should start with original

    # Save the continuation
    assert window.save_button is not None and window.save_button.isEnabled()
    window.save_button.click()
    qt_app.processEvents()

    # Verify the continuation was saved correctly
    session = temp_dataset.session
    assert session is not None
    session.refresh(original)

    children = (session.query(PromptCompletion).filter(PromptCompletion.parent_completion_id == original.id).all())
    assert len(children) == 1

    continuation = children[0]
    assert continuation.model_id == "mock-echo-model"
    assert continuation.parent_completion_id == original.id
    assert continuation.prefill == truncated_text
    assert len(continuation.completion_text) > len(truncated_text)
    assert continuation.max_tokens >= 1024  # Should use the larger max tokens

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_manual_mode_has_no_generation_controls(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> None:
    """Manual mode should not have generation controls."""

    original = _persist_completion(temp_dataset, model_id="mock-echo-model")

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.MANUAL)
    qt_app.processEvents()

    # Window title should show manual mode
    assert "Manual Edit" in window.windowTitle()

    # Should not have generation controls
    assert window.generate_button is None
    assert window.max_tokens_field is None
    assert window.context_length_field is None

    # Should still have save functionality
    assert window.save_button is not None
    assert window.new_edit is not None

    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.usefixtures("ensure_google_icon_font")
def test_continuation_mode_uses_custom_token_settings(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> None:
    """Continuation mode should use custom max tokens and context length when generating."""

    original = _persist_completion(temp_dataset, model_id="mock-echo-model")

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.CONTINUATION)
    qt_app.processEvents()

    # Set custom values
    assert window.max_tokens_field is not None
    assert window.context_length_field is not None

    custom_max_tokens = 512
    custom_context_length = 2048

    window.max_tokens_field.setValue(custom_max_tokens)
    window.context_length_field.setValue(custom_context_length)
    qt_app.processEvents()

    # Generate with custom settings
    assert window.generate_button is not None and window.generate_button.isEnabled()
    window.generate_button.click()
    qt_app.processEvents()

    # Check generation happened
    assert window.new_edit is not None
    generated_text = window.new_edit.toPlainText()
    assert len(generated_text) > 0

    # Save and check the stored parameters
    assert window.save_button is not None and window.save_button.isEnabled()
    window.save_button.click()
    qt_app.processEvents()

    # Verify saved completion uses custom parameters
    session = temp_dataset.session
    assert session is not None

    children = (session.query(PromptCompletion).filter(PromptCompletion.parent_completion_id == original.id).all())
    assert len(children) == 1

    continuation = children[0]
    assert continuation.max_tokens == custom_max_tokens
    assert continuation.context_length == custom_context_length

    window.deleteLater()
    qt_app.processEvents()
