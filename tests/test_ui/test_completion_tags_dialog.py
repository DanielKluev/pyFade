"""
Test suite for completion tags dialog functionality and WIP sorting.

Tests:
- SampleTagsDialog works for completions with scope='completions' or 'both' tags
- WIP completions are sorted first (effective rating 11)
"""
# pylint: disable=unused-argument,too-many-positional-arguments
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from PyQt6.QtWidgets import QCheckBox

from py_fade.dataset.completion import PromptCompletion, WIP_TAG_NAME
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.dataset.tag import Tag
from py_fade.gui.dialog_sample_tags import SampleTagsDialog
from tests.helpers.data_helpers import build_sample_with_completion
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase


def _create_completion(dataset: "DatasetDatabase") -> PromptCompletion:
    """
    Create and persist a PromptCompletion for testing.

    Returns the saved completion with an assigned ID.
    """
    _, completion = build_sample_with_completion(dataset)
    return completion


class TestSampleTagsDialogForCompletions:
    """Tests for using SampleTagsDialog with completions instead of samples."""

    def test_dialog_shows_completion_scoped_tags(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify dialog shows tags with scope 'completions' or 'both' for a completion target.

        Tags scoped to 'samples' only should not appear in completion tags dialog.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.scope")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        tag_completions = Tag.create(temp_dataset, "Completion::WIP", "WIP tag", scope="completions")
        tag_both = Tag.create(temp_dataset, "General Tag", "General tag", scope="both")
        tag_samples = Tag.create(temp_dataset, "Sample Only", "Sample only tag", scope="samples")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        # Should show 'completions' and 'both' tags, not 'samples' tags
        assert tag_completions.id in dialog.tag_checkboxes
        assert tag_both.id in dialog.tag_checkboxes
        assert tag_samples.id not in dialog.tag_checkboxes

        dialog.deleteLater()
        qt_app.processEvents()

    def test_dialog_shows_existing_completion_tags_checked(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify dialog pre-checks tags already assigned to the completion.

        Tags already associated with the completion should appear checked.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.existing")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        tag1 = Tag.create(temp_dataset, "Completion::WIP", "WIP tag", scope="completions")
        tag2 = Tag.create(temp_dataset, "General Tag", "General tag", scope="both")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)
        completion.add_tag(temp_dataset, tag1)
        temp_dataset.commit()

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        assert dialog.tag_checkboxes[tag1.id].isChecked()
        assert not dialog.tag_checkboxes[tag2.id].isChecked()

        dialog.deleteLater()
        qt_app.processEvents()

    def test_dialog_adds_tag_to_completion_on_accept(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify accepting dialog adds selected tags to the completion.

        Checking a tag and accepting the dialog should associate the tag with the completion.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.add")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        wip_tag = Tag.create(temp_dataset, WIP_TAG_NAME, "WIP completion tag", scope="completions")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        dialog.tag_checkboxes[wip_tag.id].setChecked(True)
        dialog.accept()
        qt_app.processEvents()

        assert completion.has_tag(temp_dataset, wip_tag)
        assert completion.is_wip(temp_dataset)

        dialog.deleteLater()
        qt_app.processEvents()

    def test_dialog_removes_tag_from_completion_on_accept(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify accepting dialog removes unchecked tags from the completion.

        Unchecking a tag and accepting the dialog should remove the tag from the completion.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.remove")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        wip_tag = Tag.create(temp_dataset, WIP_TAG_NAME, "WIP completion tag", scope="completions")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)
        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        assert completion.is_wip(temp_dataset)

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        dialog.tag_checkboxes[wip_tag.id].setChecked(False)
        dialog.accept()
        qt_app.processEvents()

        assert not completion.has_tag(temp_dataset, wip_tag)
        assert not completion.is_wip(temp_dataset)

        dialog.deleteLater()
        qt_app.processEvents()

    def test_dialog_cancel_does_not_modify_completion_tags(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify cancelling dialog does not change completion tags.

        Rejecting the dialog should leave completion tags unchanged.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.cancel")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        wip_tag = Tag.create(temp_dataset, WIP_TAG_NAME, "WIP completion tag", scope="completions")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        dialog.tag_checkboxes[wip_tag.id].setChecked(True)
        dialog.reject()
        qt_app.processEvents()

        assert not completion.has_tag(temp_dataset, wip_tag)

        dialog.deleteLater()
        qt_app.processEvents()

    def test_dialog_completion_sorts_tags_alphabetically(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify completion tags dialog sorts tags alphabetically by name.

        Tags should be displayed in alphabetical order regardless of creation order.
        """
        caplog.set_level(logging.DEBUG, logger="SampleTagsDialog")
        test_logger = logging.getLogger("test_completion_tags_dialog.sort")
        test_logger.setLevel(logging.DEBUG)
        patch_message_boxes(monkeypatch, test_logger)

        Tag.create(temp_dataset, "Completion::Zebra", "Last tag", scope="completions")
        Tag.create(temp_dataset, "Completion::Alpha", "First tag", scope="completions")
        Tag.create(temp_dataset, "Completion::Middle", "Middle tag", scope="both")
        temp_dataset.commit()

        completion = _create_completion(temp_dataset)

        dialog = SampleTagsDialog(temp_dataset, completion)
        qt_app.processEvents()

        checkbox_labels = []
        for i in range(dialog.tags_layout.count()):
            widget = dialog.tags_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                checkbox_labels.append(widget.text())

        expected_order = ["Completion::Alpha", "Completion::Middle", "Completion::Zebra"]
        assert checkbox_labels == expected_order

        dialog.deleteLater()
        qt_app.processEvents()


class TestWIPSorting:
    """Tests for WIP completion sorting behavior in WidgetSample."""

    def test_wip_completion_is_wip(self, temp_dataset: "DatasetDatabase") -> None:
        """
        Verify is_wip returns True for a completion with the WIP tag.

        Ensures the is_wip method correctly identifies WIP completions for sorting.
        """
        _, completion = build_sample_with_completion(temp_dataset)
        wip_tag = Tag.create(temp_dataset, WIP_TAG_NAME, "WIP tag", scope="completions")
        temp_dataset.commit()

        assert not completion.is_wip(temp_dataset)

        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        assert completion.is_wip(temp_dataset)

    def test_wip_effective_rating_in_sort_key(
        self,
        app_with_dataset,
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify WIP completions sort before regular rated completions.

        WIP completions should appear first in the sorted list (effective rating=11),
        even before completions with rating=10.
        """
        _ = ensure_google_icon_font
        from py_fade.dataset.completion_rating import PromptCompletionRating  # pylint: disable=import-outside-toplevel
        from py_fade.dataset.facet import Facet  # pylint: disable=import-outside-toplevel
        from py_fade.gui.widget_sample import WidgetSample  # pylint: disable=import-outside-toplevel
        from tests.helpers.data_helpers import create_test_completion  # pylint: disable=import-outside-toplevel

        dataset = app_with_dataset.current_dataset

        facet = Facet.create(dataset, "Quality Sort", "Quality facet for WIP test")
        dataset.commit()

        prompt = PromptRevision.get_or_create(dataset, "WIP sort test prompt", 2048, 512)
        sample = Sample.create_if_unique(dataset, "WIP Sort Test Sample", prompt)
        dataset.commit()

        # Create a highly-rated completion (rating=10)
        completion_high = create_test_completion(dataset.session, prompt, {"completion_text": "High rated completion"})
        dataset.commit()
        PromptCompletionRating.set_rating(dataset, completion_high, facet, 10)
        dataset.commit()

        # Create a WIP completion (no explicit rating but tagged WIP)
        completion_wip = create_test_completion(dataset.session, prompt, {"completion_text": "WIP completion text"})
        dataset.commit()
        wip_tag = Tag.create(dataset, WIP_TAG_NAME, "WIP tag", scope="completions")
        dataset.commit()
        completion_wip.add_tag(dataset, wip_tag)
        dataset.commit()

        # Use the sort function from WidgetSample
        widget = WidgetSample(None, app_with_dataset, sample)
        widget.set_active_context(facet, None)
        qt_app.processEvents()

        completions = [completion_high, completion_wip]
        sorted_completions = widget._sort_completions_by_rating_and_logprob(completions)  # pylint: disable=protected-access

        # WIP should be first even though the other has rating=10
        assert sorted_completions[0] == completion_wip
        assert sorted_completions[1] == completion_high

        widget.deleteLater()
        qt_app.processEvents()
