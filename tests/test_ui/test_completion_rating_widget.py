"""Integration-style tests for the completion rating widget."""

# pylint: disable=protected-access,too-many-positional-arguments

from __future__ import annotations

import hashlib
import logging
import pathlib
from typing import TYPE_CHECKING, Tuple

import pytest
from PyQt6.QtWidgets import QMessageBox

from py_fade.app import pyFadeApp
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from py_fade.gui.widget_sample import WidgetSample
from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow
from tests.helpers.data_helpers import create_test_completion
from tests.helpers.ui_helpers import setup_test_app_with_fake_home

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.providers.llm_response import LLMResponse


def _build_sample_with_completion(
    dataset: "DatasetDatabase",
    **completion_overrides,
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
    completion_overrides_local = {
        "sha256": hashlib.sha256(completion_text.encode("utf-8")).hexdigest(),
        "model_id": "mock-echo",
        "temperature": 0.3,
        "top_k": 1,
        "prefill": "Once upon",
        "beam_token": "upon",
        "completion_text": completion_text,
        "tags": None,
    }
    completion_overrides_local.update(completion_overrides)

    completion = create_test_completion(session, prompt_revision, completion_overrides_local)
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
    assert rating_widget.rating_record is not None
    assert rating_widget.rating_record.rating == 8
    assert rating_widget.current_rating == 8

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
    assert rating_widget.rating_record is not None
    assert rating_widget.rating_record.rating == 5
    assert rating_widget.current_rating == 5
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
    assert rating_widget.rating_record is None
    assert rating_widget.current_rating == 0

    rating_widget._on_star_clicked(4)
    qt_app.processEvents()

    rating_a = PromptCompletionRating.get(temp_dataset, completion, facet_a)
    rating_b = PromptCompletionRating.get(temp_dataset, completion, facet_b)
    assert rating_a is not None and rating_a.rating == 9
    assert rating_b is not None and rating_b.rating == 4

    widget.set_active_context(facet_a, None)
    qt_app.processEvents()
    assert rating_widget.rating_record is not None
    assert rating_widget.rating_record.rating == 9
    assert rating_widget.current_rating == 9
    tooltip_text = rating_widget.star_buttons[0].toolTip()
    assert f"{facet_a.name}: 9/10" in tooltip_text

    widget.set_active_context(None, None)
    qt_app.processEvents()
    assert rating_widget.rating_record is None
    assert rating_widget.current_rating == 0
    assert all(not button.isEnabled() for button in rating_widget.star_buttons)

    widget.deleteLater()
    qt_app.processEvents()


def test_default_facet_restored_on_dataset_reload(
    qt_app: "QApplication",
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    ensure_google_icon_font: None,
) -> None:
    """Previously selected facet should be active when reopening the dataset."""

    _ = ensure_google_icon_font

    db_path = tmp_path / "persisted_ratings.db"
    dataset = DatasetDatabase(db_path)
    dataset.initialize()

    sample, completion = _build_sample_with_completion(dataset)

    facet = Facet.create(dataset, "Persisted", "Facet persisted across sessions")
    dataset.commit()
    PromptCompletionRating.set_rating(dataset, completion, facet, 6)

    # Create test app with temporary home directory
    app = setup_test_app_with_fake_home(dataset, tmp_path, monkeypatch)
    widget = WidgetDatasetTop(None, app, dataset)
    qt_app.processEvents()

    try:
        assert widget.facet_combo is not None
        facet_index = widget.facet_combo.findData(facet.id)
        assert facet_index >= 0
        widget.facet_combo.setCurrentIndex(facet_index)
        widget._on_facet_selection_changed(facet_index)  # pylint: disable=protected-access
        qt_app.processEvents()
    finally:
        widget.deleteLater()
        qt_app.processEvents()
        app.current_dataset = None

    dataset.dispose()

    reopened_dataset = DatasetDatabase(db_path)
    reopened_dataset.initialize()

    # Create another config path for the reopened app
    config_path_reopened = tmp_path / "home" / "config_reopened.yaml"
    app_reopened = pyFadeApp(config_path=config_path_reopened)
    app_reopened.current_dataset = reopened_dataset
    widget_reopened = WidgetDatasetTop(None, app_reopened, reopened_dataset)
    qt_app.processEvents()

    try:
        assert widget_reopened.current_facet is not None
        assert widget_reopened.current_facet.id == facet.id

        session = reopened_dataset.session
        assert session is not None
        sample_reloaded = session.get(Sample, sample.id)
        assert sample_reloaded is not None

        widget_reopened._open_sample_by_id(sample_reloaded.id)  # pylint: disable=protected-access
        qt_app.processEvents()

        sample_widgets = [
            info["widget"] for info in widget_reopened.tabs.values() if info["type"] == "sample" and info["id"] == sample_reloaded.id
        ]
        assert sample_widgets, "Expected sample tab with persisted completion"
        reloaded_sample_widget = sample_widgets[0]

        frame = _first_completion_frame(reloaded_sample_widget)
        rating_widget = frame.rating_widget

        assert all(button.isEnabled() for button in rating_widget.star_buttons)
        assert rating_widget.rating_record is not None
        assert rating_widget.rating_record.rating == 6
        assert rating_widget.current_rating == 6
    finally:
        widget_reopened.deleteLater()
        qt_app.processEvents()
        app_reopened.current_dataset = None
        reopened_dataset.dispose()


def test_archive_button_hides_completion_until_toggle_enabled(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
) -> None:
    """Archiving a completion hides it unless the archived toggle is enabled."""

    _ = ensure_google_icon_font

    sample, completion = _build_sample_with_completion(temp_dataset)

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    archive_events: list[tuple[PromptCompletion, bool]] = []
    widget.completion_archive_toggled.connect(lambda completion_obj, archived: archive_events.append((completion_obj, archived)))

    frame = _first_completion_frame(widget)
    assert frame.archive_button is not None
    frame.archive_button.click()
    qt_app.processEvents()

    assert archive_events, "Archive signal should fire when toggled"
    assert archive_events[0][0].id == completion.id
    assert archive_events[0][1] is True
    assert completion.is_archived is True

    with pytest.raises(AssertionError):
        _first_completion_frame(widget)

    widget.show_archived_checkbox.setChecked(True)
    qt_app.processEvents()

    archived_frame = _first_completion_frame(widget)
    assert isinstance(archived_frame.completion, PromptCompletion)
    assert archived_frame.completion.is_archived is True
    assert archived_frame.archive_button is not None

    archived_frame.archive_button.click()
    qt_app.processEvents()

    assert archive_events[-1][1] is False
    assert completion.is_archived is False

    widget.show_archived_checkbox.setChecked(False)
    qt_app.processEvents()
    unarchived_frame = _first_completion_frame(widget)
    assert isinstance(unarchived_frame.completion, PromptCompletion)
    assert unarchived_frame.completion.is_archived is False

    widget.deleteLater()
    qt_app.processEvents()


def test_resume_button_emits_signal_for_truncated_completion(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Truncated completions surface a resume action that emits through WidgetSample."""

    _ = ensure_google_icon_font

    sample, completion = _build_sample_with_completion(temp_dataset, is_truncated=True)

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    # Mock exec to avoid actual dialog showing
    monkeypatch.setattr(ThreeWayCompletionEditorWindow, "exec", lambda self: 0)

    resume_events: list[PromptCompletion] = []
    widget.completion_resume_requested.connect(resume_events.append)

    frame = _first_completion_frame(widget)
    assert frame.resume_button is not None
    assert not frame.resume_button.isHidden()

    frame.resume_button.click()
    qt_app.processEvents()

    assert resume_events and resume_events[0].id == completion.id

    widget.deleteLater()
    qt_app.processEvents()


def test_resume_button_should_open_three_way_editor(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume button should open ThreeWayCompletionEditorWindow like edit button does."""

    _ = ensure_google_icon_font

    sample, _ = _build_sample_with_completion(temp_dataset, is_truncated=True)

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    # Track if ThreeWayCompletionEditorWindow is created
    editor_instances: list[ThreeWayCompletionEditorWindow] = []
    original_init = ThreeWayCompletionEditorWindow.__init__

    def mock_init(self, *args, **kwargs):
        editor_instances.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(ThreeWayCompletionEditorWindow, "__init__", mock_init)

    # Mock exec to avoid actual dialog showing
    monkeypatch.setattr(ThreeWayCompletionEditorWindow, "exec", lambda self: 0)

    frame = _first_completion_frame(widget)
    assert frame.resume_button is not None
    assert not frame.resume_button.isHidden()

    # Click resume button - this should open ThreeWayCompletionEditorWindow
    frame.resume_button.click()
    qt_app.processEvents()

    # Verify that ThreeWayCompletionEditorWindow was created
    assert len(editor_instances) == 1, "ThreeWayCompletionEditorWindow should be created when resume is clicked"

    widget.deleteLater()
    qt_app.processEvents()


def test_evaluate_button_respects_logprob_availability(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,
) -> None:
    """Evaluate button appears only when logprobs for the target model are missing."""

    _ = ensure_google_icon_font

    sample, completion = _build_sample_with_completion(temp_dataset)

    widget = WidgetSample(None, app_with_dataset, sample)
    qt_app.processEvents()

    widget.set_active_context(None, "mock-echo-model (mock)")
    qt_app.processEvents()

    evaluate_events: list[tuple[PromptCompletion, str]] = []
    widget.completion_evaluate_requested.connect(lambda completion_obj, model_name: evaluate_events.append((completion_obj, model_name)))

    frame = _first_completion_frame(widget)
    assert frame.evaluate_button is not None
    assert not frame.evaluate_button.isHidden()

    frame.evaluate_button.click()
    qt_app.processEvents()

    assert evaluate_events and evaluate_events[0][0].id == completion.id
    assert evaluate_events[0][1] == "mock-echo-model"

    session = temp_dataset.session
    assert session is not None
    session.add(
        PromptCompletionLogprobs(
            prompt_completion_id=completion.id,
            logprobs_model_id="mock-echo-model",
            logprobs=[{
                "token": "a",
                "logprob": -1.0,
                "top_logprobs": []
            }],
            min_logprob=-1.0,
            avg_logprob=-1.0,
        ))
    session.commit()
    session.refresh(completion)

    widget.populate_outputs()
    qt_app.processEvents()

    refreshed_frame = _first_completion_frame(widget)
    assert refreshed_frame.evaluate_button is not None
    assert refreshed_frame.evaluate_button.isHidden()

    widget.deleteLater()
    qt_app.processEvents()
