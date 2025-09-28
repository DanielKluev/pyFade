"""
Test suite for WidgetTag GUI component.

Tests tag creation, editing, deletion, validation, and navigation functionality.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

import pytest

from py_fade.dataset.tag import Tag
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from py_fade.gui.widget_tag import WidgetTag
from tests.helpers.ui_helpers import patch_message_boxes
from tests.helpers.data_helpers import setup_widget_test_environment

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def test_widget_tag_crud_flow(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test complete CRUD operations for tags through the WidgetTag interface.

    Verifies creation, reading, updating, and deletion of tags with proper
    validation and UI state management.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetTag")
    test_logger = logging.getLogger("test_widget_tag.crud")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetTag(None, app_with_dataset, temp_dataset, None)
    widget.tag_saved.connect(lambda tag: test_logger.debug("tag_saved id=%s", getattr(tag, "id", None)))
    widget.tag_deleted.connect(lambda tag: test_logger.debug("tag_deleted id=%s", getattr(tag, "id", None)))

    qt_app.processEvents()

    assert widget.tag is None
    assert not widget.delete_button.isVisible()

    widget.name_field.setText("Important")
    widget.description_field.setPlainText("Important tag used for critical reviews")
    completions_index = widget.scope_combo.findData("completions")
    assert completions_index >= 0
    widget.scope_combo.setCurrentIndex(completions_index)
    qt_app.processEvents()

    assert widget.save_button.isEnabled()

    widget.handle_save()
    qt_app.processEvents()

    created_tag = Tag.get_by_name(temp_dataset, "Important")
    assert created_tag is not None
    assert widget.tag is not None and widget.tag.id == created_tag.id
    assert created_tag.scope == "completions"
    assert "Creating tag" in caplog.text

    samples_index = widget.scope_combo.findData("samples")
    assert samples_index >= 0
    widget.scope_combo.setCurrentIndex(samples_index)
    widget.description_field.setPlainText("Updated description for the important tag")
    qt_app.processEvents()
    widget.handle_save()
    qt_app.processEvents()

    refreshed_tag = Tag.get_by_id(temp_dataset, created_tag.id)
    assert refreshed_tag is not None
    assert refreshed_tag.description == "Updated description for the important tag"
    assert refreshed_tag.scope == "samples"

    widget.handle_delete()
    qt_app.processEvents()

    assert Tag.get_by_id(temp_dataset, created_tag.id) is None
    assert widget.tag is None
    assert not widget.delete_button.isVisible()
    assert widget.scope_combo.currentData() == Tag.DEFAULT_SCOPE

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_tag_validation_prevents_duplicates(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test tag name validation prevents duplicate names.

    Verifies that the widget properly validates unique tag names and shows
    appropriate error messages when duplicates are attempted.
    """
    Tag.create(temp_dataset, "Alpha", "Existing alpha tag")
    session = temp_dataset.session
    assert session is not None
    session.flush()
    session.commit()

    caplog.set_level(logging.DEBUG, logger="WidgetTag")
    test_logger = logging.getLogger("test_widget_tag.validation")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetTag(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    widget.name_field.setText("Alpha")
    widget.description_field.setPlainText("Makes duplicates invalid")
    qt_app.processEvents()

    assert not widget.save_button.isEnabled()
    assert not widget.validation_label.isHidden()
    assert "Name must be unique" in widget.validation_label.text()

    widget.name_field.setText("Beta")
    qt_app.processEvents()

    assert widget.scope_combo.currentData() == Tag.DEFAULT_SCOPE
    assert widget.save_button.isEnabled()
    assert widget.validation_label.isHidden()

    widget.deleteLater()
    qt_app.processEvents()


def test_navigation_opens_tag_tab(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test navigation from sidebar opens appropriate tag tabs.

    Verifies that clicking on tags in the navigation sidebar opens the correct
    tag editing interface with proper state initialization.
    """
    logger = logging.getLogger("test_widget_tag.navigation")
    logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, logger)

    tag = Tag.create(temp_dataset, "Review", "Marks samples for peer review")
    
    widget = setup_widget_test_environment(temp_dataset, app_with_dataset, qt_app)

    widget.sidebar.filter_panel.show_combo.setCurrentText("Tags")
    qt_app.processEvents()

    widget.sidebar.tree_view.item_selected.emit("tag", tag.id)
    qt_app.processEvents()

    existing_widget_id = widget._find_tab_by("tag", tag.id)  # pylint: disable=protected-access
    assert existing_widget_id is not None
    tab_info = widget.tabs[existing_widget_id]
    assert isinstance(tab_info["widget"], WidgetTag)
    assert tab_info["widget"].scope_combo.currentData() == tag.scope

    widget.sidebar.tree_view.new_item_requested.emit("Tag")
    qt_app.processEvents()

    new_tab_ids: List[Tuple[int, dict]] = [
        (wid, info) for wid, info in widget.tabs.items() if info["type"] == "tag" and info["id"] == 0
    ]
    assert new_tab_ids, "Expected a new unsaved tag tab to be created"
    for _, info in new_tab_ids:
        new_widget = info["widget"]
        assert isinstance(new_widget, WidgetTag)
        assert new_widget.scope_combo.currentData() == Tag.DEFAULT_SCOPE

    widget.deleteLater()
    qt_app.processEvents()
