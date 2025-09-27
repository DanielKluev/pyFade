"""Integration tests for the three-way completion editor window."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow

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
) -> PromptCompletion:
    """Create and commit a ``PromptCompletion`` attached to a prompt revision."""

    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, _DEF_PROMPT, 2048, 128)

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
        max_tokens=128,
        is_truncated=False,
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

    children = (
        session.query(PromptCompletion)
        .filter(PromptCompletion.parent_completion_id == original.id)
        .all()
    )
    assert len(children) == 1

    new_completion = children[0]
    assert new_completion.model_id == "manual"
    assert new_completion.parent_completion_id == original.id
    assert new_completion.completion_text.endswith("Rewritten for clarity.")
    assert original.is_archived is True

    preferred_rating = PromptCompletionRating.get(temp_dataset, new_completion, facet)
    assert preferred_rating is not None and preferred_rating.rating == 10
    discouraged_rating = PromptCompletionRating.get(temp_dataset, original, facet)
    assert discouraged_rating is not None and discouraged_rating.rating == 2

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

    window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original)
    qt_app.processEvents()

    assert window.generate_radio is not None
    window.generate_radio.setChecked(True)
    qt_app.processEvents()

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

    children = (
        session.query(PromptCompletion)
        .filter(PromptCompletion.parent_completion_id == original.id)
        .all()
    )
    assert len(children) == 1

    continuation = children[0]
    assert continuation.model_id == "mock-echo-model"
    assert continuation.parent_completion_id == original.id
    assert continuation.prefill == original.completion_text
    assert continuation.is_archived is False

    window.deleteLater()
    qt_app.processEvents()
