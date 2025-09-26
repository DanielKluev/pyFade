"""Integration-style tests for the completion rating widget."""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Tuple

import pytest
from PyQt6.QtWidgets import QMessageBox

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.widget_completion import CompletionFrame
from py_fade.gui.widget_sample import WidgetSample

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.providers.llm_response import LLMResponse


def _build_sample_with_completion(
    dataset: "DatasetDatabase",
) -> Tuple[Sample, PromptCompletion]:
    """Create a persisted sample with a single completion for tests."""

    session = dataset.session
    assert session is not None

    prompt_revision = PromptRevision.get_or_create(dataset, "Once upon", 2048, 128)
    sample = Sample.create_if_unique(dataset, "Rating sample", prompt_revision, None)
    if sample is None:
        sample = Sample.from_prompt_revision(dataset, prompt_revision)
        session.add(sample)
        session.commit()

    completion_text = "Once upon a midnight dreary, while I pondered, weak and weary."
    completion = PromptCompletion(
        prompt_revision=prompt_revision,
        sha256=hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
        model_id="mock-echo",
        temperature=0.3,
        top_k=1,
        prefill="Once upon",
        beam_token="upon",
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

    return sample, completion


def _first_completion_frame(widget: WidgetSample) -> CompletionFrame:
    for index in range(widget.output_layout.count()):
        item = widget.output_layout.itemAt(index)
        child = item.widget() if item is not None else None
        if isinstance(child, CompletionFrame):
            return child
    raise AssertionError("No CompletionFrame found in widget outputs")


def test_rating_saved_and_updated(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A user can save and update a completion rating with confirmation prompts."""

    _ = ensure_google_icon_font
    caplog.set_level(logging.DEBUG, logger="CompletionRatingWidget")

    sample, completion = _build_sample_with_completion(temp_dataset)

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    facet = Facet.create(temp_dataset, "Quality", "Overall answer quality")
    temp_dataset.commit()

    widget.set_active_context(facet, None)
    qt_app.processEvents()

    frame = _first_completion_frame(widget)
    rating_widget = frame.rating_widget

    assert rating_widget.rating_record is None
    rating_widget._on_star_clicked(8)
    qt_app.processEvents()

    saved_rating = PromptCompletionRating.get(temp_dataset, completion, facet)
    assert saved_rating is not None and saved_rating.rating == 8
    assert rating_widget.rating_value_label.text() == "8 / 10"
    assert "Saved 8/10" in rating_widget.helper_label.text()

    questions: list[tuple] = []

    def _confirm(*args, **kwargs):
        questions.append((args, kwargs))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_confirm))

    rating_widget._on_star_clicked(5)
    qt_app.processEvents()

    assert questions, "Expected confirmation prompt when updating existing rating"
    updated_rating = PromptCompletionRating.get(temp_dataset, completion, facet)
    assert updated_rating is not None and updated_rating.rating == 5
    assert rating_widget.rating_value_label.text() == "5 / 10"
    tooltip_text = rating_widget.star_buttons[0].toolTip()
    assert f"{facet.name}: 5/10" in tooltip_text

    widget.deleteLater()
    qt_app.processEvents()


def test_rating_is_scoped_per_facet(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switching facets swaps the displayed rating based on per-facet persistence."""

    _ = ensure_google_icon_font

    sample, completion = _build_sample_with_completion(temp_dataset)

    facet_a = Facet.create(temp_dataset, "Tone", "Tone alignment")
    facet_b = Facet.create(temp_dataset, "Safety", "Safety review")
    temp_dataset.commit()

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    frame = _first_completion_frame(widget)
    rating_widget = frame.rating_widget

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
    )

    widget.set_active_context(facet_a, None)
    qt_app.processEvents()
    rating_widget._on_star_clicked(9)
    qt_app.processEvents()

    widget.set_active_context(facet_b, None)
    qt_app.processEvents()
    assert rating_widget.rating_record is None
    assert rating_widget.rating_value_label.text() == "Not rated"

    rating_widget._on_star_clicked(4)
    qt_app.processEvents()

    rating_a = PromptCompletionRating.get(temp_dataset, completion, facet_a)
    rating_b = PromptCompletionRating.get(temp_dataset, completion, facet_b)
    assert rating_a is not None and rating_a.rating == 9
    assert rating_b is not None and rating_b.rating == 4

    widget.set_active_context(facet_a, None)
    qt_app.processEvents()
    assert rating_widget.rating_value_label.text() == "9 / 10"
    tooltip_text = rating_widget.star_buttons[0].toolTip()
    assert f"{facet_a.name}: 9/10" in tooltip_text

    widget.set_active_context(None, None)
    qt_app.processEvents()
    assert rating_widget.rating_value_label.text() == "-- / 10"

    widget.deleteLater()
    qt_app.processEvents()
