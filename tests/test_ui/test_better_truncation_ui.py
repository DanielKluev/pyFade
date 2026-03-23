"""
UI tests for the Better Truncation feature.

Covers:
- Toggle Truncation State action in CompletionFrame context menu
- Mark as Truncated checkbox in ThreeWayCompletionEditorWindow
- allow_truncated checkbox in WidgetExportTemplate
"""

# pylint: disable=protected-access

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.prompt import PromptRevision
from py_fade.gui.components.widget_completion import CompletionFrame
from py_fade.gui.window_three_way_completion_editor import ThreeWayCompletionEditorWindow, EditorMode
from tests.helpers.data_helpers import build_sample_with_completion

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
    """
    Create and commit a PromptCompletion attached to a prompt revision.
    """
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


# ---------------------------------------------------------------------------
# Toggle Truncation State in CompletionFrame
# ---------------------------------------------------------------------------
class TestCompletionFrameToggleTruncation:
    """
    Tests for the 'Toggle Truncation State' action in the CompletionFrame context menu.
    """

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_toggle_truncation_marks_full_as_truncated(self, temp_dataset: "DatasetDatabase", qt_app: "QApplication") -> None:
        """
        Toggling truncation on a non-truncated completion should set is_truncated=True
        and update the status icons.
        """
        _, completion = build_sample_with_completion(temp_dataset, is_truncated=False)
        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert not completion.is_truncated

        frame._toggle_truncation_state()
        qt_app.processEvents()

        assert completion.is_truncated is True
        # Verify change is persisted by re-querying
        session = temp_dataset.get_session()
        reloaded = session.get(PromptCompletion, completion.id)
        assert reloaded.is_truncated is True

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_toggle_truncation_marks_truncated_as_full(self, temp_dataset: "DatasetDatabase", qt_app: "QApplication") -> None:
        """
        Toggling truncation on a truncated completion should set is_truncated=False
        and update the status icons.
        """
        _, completion = build_sample_with_completion(temp_dataset, is_truncated=True)
        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert completion.is_truncated is True

        frame._toggle_truncation_state()
        qt_app.processEvents()

        assert completion.is_truncated is False
        session = temp_dataset.get_session()
        reloaded = session.get(PromptCompletion, completion.id)
        assert reloaded.is_truncated is False

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_toggle_truncation_double_toggle_restores_state(self, temp_dataset: "DatasetDatabase", qt_app: "QApplication") -> None:
        """
        Toggling truncation twice should restore the original state.
        """
        _, completion = build_sample_with_completion(temp_dataset, is_truncated=False)
        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        frame._toggle_truncation_state()
        qt_app.processEvents()
        assert completion.is_truncated is True

        frame._toggle_truncation_state()
        qt_app.processEvents()
        assert completion.is_truncated is False


# ---------------------------------------------------------------------------
# Mark as Truncated in ThreeWayCompletionEditorWindow
# ---------------------------------------------------------------------------
class TestThreeWayEditorMarkTruncated:
    """
    Tests for the 'Mark new completion as truncated' checkbox in the
    ThreeWayCompletionEditorWindow.
    """

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_mark_truncated_checkbox_exists(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                            qt_app: "QApplication") -> None:
        """
        The editor window should have a 'mark_truncated_checkbox' attribute.
        """
        original = _persist_completion(temp_dataset)
        facet = Facet.create(temp_dataset, "Accuracy", "desc")
        temp_dataset.commit()

        window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.MANUAL, facet=facet)
        qt_app.processEvents()

        assert window.mark_truncated_checkbox is not None
        assert not window.mark_truncated_checkbox.isChecked()

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_mark_truncated_checkbox_off_saves_non_truncated(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                             qt_app: "QApplication", caplog: pytest.LogCaptureFixture) -> None:
        """
        With mark_truncated unchecked, saved completion has is_truncated=False.
        """
        caplog.set_level(logging.DEBUG, logger="ThreeWayCompletionEditorWindow")

        original = _persist_completion(temp_dataset)
        facet = Facet.create(temp_dataset, "Accuracy", "desc")
        temp_dataset.commit()

        window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.MANUAL, facet=facet)
        qt_app.processEvents()

        window.mark_truncated_checkbox.setChecked(False)
        window.new_edit.setPlainText(original.completion_text + "\nExtra text")
        qt_app.processEvents()

        window.save_button.click()
        qt_app.processEvents()

        # Find the new completion
        session = temp_dataset.get_session()
        completions = session.query(PromptCompletion).filter(PromptCompletion.id != original.id).all()
        assert len(completions) == 1
        assert completions[0].is_truncated is False

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_mark_truncated_checkbox_on_saves_truncated(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                        qt_app: "QApplication", caplog: pytest.LogCaptureFixture) -> None:
        """
        With mark_truncated checked, saved completion has is_truncated=True.
        """
        caplog.set_level(logging.DEBUG, logger="ThreeWayCompletionEditorWindow")

        original = _persist_completion(temp_dataset)
        facet = Facet.create(temp_dataset, "Accuracy", "desc")
        temp_dataset.commit()

        window = ThreeWayCompletionEditorWindow(app_with_dataset, temp_dataset, original, EditorMode.MANUAL, facet=facet)
        qt_app.processEvents()

        window.mark_truncated_checkbox.setChecked(True)
        window.new_edit.setPlainText(original.completion_text + "\nTruncated edit")
        qt_app.processEvents()

        window.save_button.click()
        qt_app.processEvents()

        session = temp_dataset.get_session()
        completions = session.query(PromptCompletion).filter(PromptCompletion.id != original.id).all()
        assert len(completions) == 1
        assert completions[0].is_truncated is True


# ---------------------------------------------------------------------------
# WidgetExportTemplate allow_truncated checkbox
# ---------------------------------------------------------------------------
class TestWidgetExportTemplateAllowTruncated:
    """
    Tests for the allow_truncated checkbox in the WidgetExportTemplate form.
    """

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_allow_truncated_checkbox_exists(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                             qt_app: "QApplication") -> None:
        """
        The widget should expose an allow_truncated_checkbox attribute.
        """
        from py_fade.gui.widget_export_template import WidgetExportTemplate  # pylint: disable=import-outside-toplevel
        widget = WidgetExportTemplate(None, app_with_dataset, temp_dataset, None)
        widget.show()
        qt_app.processEvents()

        assert hasattr(widget, "allow_truncated_checkbox")
        assert widget.allow_truncated_checkbox is not None

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_new_template_defaults_unchecked(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                             qt_app: "QApplication") -> None:
        """
        For a new template, the allow_truncated checkbox should be unchecked.
        """
        from py_fade.gui.widget_export_template import WidgetExportTemplate  # pylint: disable=import-outside-toplevel
        widget = WidgetExportTemplate(None, app_with_dataset, temp_dataset, None)
        widget.set_template(None)
        qt_app.processEvents()

        assert not widget.allow_truncated_checkbox.isChecked()

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def test_existing_template_loads_checkbox_state(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                    qt_app: "QApplication") -> None:
        """
        Loading an existing template with allow_truncated=True should check the checkbox.
        """
        from py_fade.gui.widget_export_template import WidgetExportTemplate  # pylint: disable=import-outside-toplevel

        facet = Facet.create(temp_dataset, "F-UI", "desc")
        temp_dataset.commit()

        template = ExportTemplate.create(
            temp_dataset,
            name="T-UI-Load",
            description="d",
            training_type="SFT",
            output_format="JSONL (ShareGPT)",
            model_families=["Llama3"],
            allow_truncated=True,
            facets=[{
                "facet_id": facet.id,
                "limit_type": "percentage",
                "limit_value": 100,
                "order": "random",
            }],
        )
        temp_dataset.commit()

        widget = WidgetExportTemplate(None, app_with_dataset, temp_dataset, template)
        qt_app.processEvents()

        assert widget.allow_truncated_checkbox.isChecked()

    @pytest.mark.usefixtures("ensure_google_icon_font")
    def testcollect_form_data_includes_allow_truncated(self, app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase",
                                                       qt_app: "QApplication") -> None:
        """
        collect_form_data() includes the allow_truncated key from the checkbox state.
        """
        from py_fade.gui.widget_export_template import WidgetExportTemplate  # pylint: disable=import-outside-toplevel
        widget = WidgetExportTemplate(None, app_with_dataset, temp_dataset, None)
        widget.set_template(None)
        qt_app.processEvents()

        # Default unchecked
        data = widget.collect_form_data()
        assert "allow_truncated" in data
        assert data["allow_truncated"] is False

        # Toggle and re-gather
        widget.allow_truncated_checkbox.setChecked(True)
        qt_app.processEvents()
        data = widget.collect_form_data()
        assert data["allow_truncated"] is True
