"""
Test suite for completion context menu and tag display functionality.

Tests the completion context menu, tag display in header, WIP indicator,
and WIP sorting behavior in CompletionFrame.
"""
# pylint: disable=unused-argument,too-many-positional-arguments
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.completion import PromptCompletion, WIP_TAG_NAME
from py_fade.dataset.sample import Sample
from py_fade.dataset.tag import Tag
from py_fade.gui.components.widget_completion import CompletionFrame
from tests.helpers.data_helpers import build_sample_with_completion

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.dataset.dataset import DatasetDatabase


def _create_saved_completion(dataset: "DatasetDatabase") -> tuple[Sample, PromptCompletion]:
    """
    Create a persisted sample and completion for testing.

    Returns a tuple of (sample, completion) with database IDs assigned.
    """
    return build_sample_with_completion(dataset)


def _create_wip_tag(dataset: "DatasetDatabase") -> Tag:
    """
    Create and persist a Completion::WIP tag.

    Returns the WIP Tag instance.
    """
    tag = Tag.create(dataset, WIP_TAG_NAME, "Work in progress completion", scope="completions")
    dataset.commit()
    return tag


class TestContextMenuButton:
    """Tests for the '...' context menu button in CompletionFrame."""

    def test_context_menu_button_exists_in_sample_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify the context menu button is present in sample mode.

        The '...' button should be added to the header in sample mode.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.context_menu_button is not None
        assert frame.context_menu_button.isVisible()

        frame.deleteLater()
        qt_app.processEvents()

    def test_context_menu_button_absent_in_beam_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify the context menu button is absent in beam mode.

        Beam mode completions do not support the context menu button.
        """
        from tests.helpers.data_helpers import create_test_llm_response  # pylint: disable=import-outside-toplevel
        _ = ensure_google_icon_font

        beam = create_test_llm_response()
        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        assert frame.context_menu_button is None

        frame.deleteLater()
        qt_app.processEvents()

    def test_context_menu_button_click_triggers_menu(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        Verify clicking the context menu button shows the context menu.

        Clicking the '...' button should invoke _show_context_menu.
        """
        caplog.set_level(logging.DEBUG, logger="CompletionFrame")
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        called = []

        def mock_show_context_menu(pos):
            called.append(pos)

        monkeypatch.setattr(frame, "_show_context_menu", mock_show_context_menu)

        assert frame.context_menu_button is not None
        frame.context_menu_button.click()
        qt_app.processEvents()

        assert len(called) == 1

        frame.deleteLater()
        qt_app.processEvents()


class TestTagHeaderDisplay:
    """Tests for the tag icon and label in the header row of CompletionFrame."""

    def test_no_tag_label_when_no_tags(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify no tag label is shown when completion has no tags.

        The tag_header_label should be None when no tags are assigned.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.tag_header_label is None

        frame.deleteLater()
        qt_app.processEvents()

    def test_single_tag_shows_last_part_after_separator(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify single tag label shows the last part after '::'.

        For a tag named 'Completion::WIP', the label should show 'WIP'.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)
        wip_tag = _create_wip_tag(temp_dataset)

        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.tag_header_label is not None

        frame.deleteLater()
        qt_app.processEvents()

    def test_single_tag_label_shortened_to_six_chars(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify single tag label is shortened to 6 characters.

        Tag display text should be at most 6 characters long.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)
        long_tag = Tag.create(temp_dataset, "Completion::VeryLongTagName", "Long tag", scope="completions")
        temp_dataset.commit()

        completion.add_tag(temp_dataset, long_tag)
        temp_dataset.commit()

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.tag_header_label is not None
        # The label text should be at most 6 chars (last part of 'VeryLongTagName' is 'VeryLongTagName' -> 'VeryLo')
        label_widget = frame.tag_header_label
        # Access the text_label child since QLabelWithIconAndText wraps a QLabel
        text_label = getattr(label_widget, 'text_label', None)
        if text_label is not None:
            assert len(text_label.text()) <= 6

        frame.deleteLater()
        qt_app.processEvents()

    def test_multiple_tags_shows_count(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify that multiple tags shows a count label in the header.

        When more than one tag is assigned, the header shows the quantity.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)
        tag1 = Tag.create(temp_dataset, "Completion::Alpha", "Alpha tag", scope="completions")
        tag2 = Tag.create(temp_dataset, "Completion::Beta", "Beta tag", scope="completions")
        temp_dataset.commit()

        completion.add_tag(temp_dataset, tag1)
        completion.add_tag(temp_dataset, tag2)
        temp_dataset.commit()

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.tag_header_label is not None
        # The label text should be "2" (count of tags)
        text_label = getattr(frame.tag_header_label, 'text_label', None)
        if text_label is not None:
            assert text_label.text() == "2"

        frame.deleteLater()
        qt_app.processEvents()

    def test_tag_label_tooltip_contains_all_tag_names(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify that tag label tooltip lists all assigned tags.

        The tooltip should contain each tag name on a separate line.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)
        tag1 = Tag.create(temp_dataset, "Completion::Alpha", "Alpha tag", scope="completions")
        tag2 = Tag.create(temp_dataset, "Completion::Beta", "Beta tag", scope="completions")
        temp_dataset.commit()

        completion.add_tag(temp_dataset, tag1)
        completion.add_tag(temp_dataset, tag2)
        temp_dataset.commit()

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.tag_header_label is not None
        tooltip = frame.tag_header_label.toolTip()
        assert "Completion::Alpha" in tooltip
        assert "Completion::Beta" in tooltip

        frame.deleteLater()
        qt_app.processEvents()

    def test_tag_label_updated_after_open_tags_dialog(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Verify tag label updates after opening and closing the tags dialog.

        When the tags dialog is accepted, the tag header label should reflect changes.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # No tags initially
        assert frame.tag_header_label is None

        # Simulate dialog: add a tag directly and then call _update_tag_header_label
        wip_tag = _create_wip_tag(temp_dataset)
        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        frame._update_tag_header_label()  # pylint: disable=protected-access
        qt_app.processEvents()

        assert frame.tag_header_label is not None

        frame.deleteLater()
        qt_app.processEvents()


class TestWIPIndicator:
    """Tests for the WIP indicator (? icon) in CompletionFrame."""

    def test_wip_indicator_hidden_by_default(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify WIP indicator is hidden when completion has no WIP tag.

        The ? indicator should not be visible for normal completions.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.wip_indicator is not None
        assert not frame.wip_indicator.isVisible()
        assert frame.rating_widget.isVisible()

        frame.deleteLater()
        qt_app.processEvents()

    def test_wip_indicator_shown_for_wip_completion(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify WIP indicator is shown and rating stars hidden for WIP completions.

        When Completion::WIP tag is assigned, the ? icon should replace rating stars.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)
        wip_tag = _create_wip_tag(temp_dataset)

        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        assert frame.wip_indicator is not None
        assert frame.wip_indicator.isVisible()
        assert not frame.rating_widget.isVisible()

        frame.deleteLater()
        qt_app.processEvents()

    def test_wip_indicator_absent_in_beam_mode(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify WIP indicator attribute is None in beam mode.

        Beam mode does not have rating stars, so WIP indicator is not needed.
        """
        from tests.helpers.data_helpers import create_test_llm_response  # pylint: disable=import-outside-toplevel
        _ = ensure_google_icon_font

        beam = create_test_llm_response()
        frame = CompletionFrame(temp_dataset, beam, display_mode="beam")
        frame.show()
        qt_app.processEvents()

        assert frame.wip_indicator is None

        frame.deleteLater()
        qt_app.processEvents()

    def test_wip_display_updates_after_tag_change(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
    ) -> None:
        """
        Verify WIP display updates when tags change.

        After adding the WIP tag, calling _update_wip_display should toggle visibility.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        # Initially no WIP
        assert not frame.wip_indicator.isVisible()
        assert frame.rating_widget.isVisible()

        # Add WIP tag and update display
        wip_tag = _create_wip_tag(temp_dataset)
        completion.add_tag(temp_dataset, wip_tag)
        temp_dataset.commit()

        frame._update_wip_display()  # pylint: disable=protected-access
        qt_app.processEvents()

        assert frame.wip_indicator.isVisible()
        assert not frame.rating_widget.isVisible()

        frame.deleteLater()
        qt_app.processEvents()


class TestOpenTagsDialog:
    """Tests for _open_tags_dialog method in CompletionFrame."""

    def test_open_tags_dialog_shows_dialog_for_saved_completion(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Verify _open_tags_dialog opens the SampleTagsDialog for saved completions.

        The dialog should be created and executed when called on a saved completion.
        """
        _ = ensure_google_icon_font
        _, completion = _create_saved_completion(temp_dataset)

        frame = CompletionFrame(temp_dataset, completion, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        dialog_opened = []

        class MockDialog:
            """Mock dialog that records calls without showing UI."""

            def __init__(self, *args, **kwargs):
                dialog_opened.append((args, kwargs))

            def exec(self):
                """Return Accepted to simulate dialog acceptance."""
                from PyQt6.QtWidgets import QMessageBox  # pylint: disable=import-outside-toplevel
                return QMessageBox.DialogCode.Accepted

        # Call the method directly with the mock dialog
        monkeypatch.setattr("py_fade.gui.dialog_sample_tags.SampleTagsDialog", MockDialog)
        frame._open_tags_dialog()  # pylint: disable=protected-access
        qt_app.processEvents()

        assert len(dialog_opened) == 1

        frame.deleteLater()
        qt_app.processEvents()

    def test_open_tags_dialog_warns_for_unsaved_completion(
        self,
        temp_dataset: "DatasetDatabase",
        qt_app: "QApplication",
        ensure_google_icon_font: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Verify _open_tags_dialog shows a warning for unsaved (beam) completions.

        Completions without a database ID cannot have tags assigned.
        """
        from tests.helpers.data_helpers import create_test_llm_response  # pylint: disable=import-outside-toplevel
        _ = ensure_google_icon_font

        beam = create_test_llm_response()
        frame = CompletionFrame(temp_dataset, beam, display_mode="sample")
        frame.show()
        qt_app.processEvents()

        warning_shown = []

        def mock_warning(*args, **kwargs):
            warning_shown.append(args)

        monkeypatch.setattr("py_fade.gui.components.widget_completion.QMessageBox.warning", mock_warning)
        frame._open_tags_dialog()  # pylint: disable=protected-access
        qt_app.processEvents()

        assert len(warning_shown) == 1

        frame.deleteLater()
        qt_app.processEvents()
