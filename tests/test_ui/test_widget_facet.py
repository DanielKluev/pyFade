"""
Test suite for WidgetFacet GUI component.

Tests facet creation, editing, deletion, validation, and navigation functionality.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.facet import Facet
from py_fade.gui.widget_facet import WidgetFacet
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def test_widget_facet_crud_flow(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test complete CRUD operations for facets through the WidgetFacet interface.
    
    Verifies creation, reading, updating, and deletion of facets with proper 
    validation and UI state management.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetFacet")
    test_logger = logging.getLogger("test_widget_facet.crud")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetFacet(None, app_with_dataset, temp_dataset, None)
    widget.facet_saved.connect(lambda facet: test_logger.debug("facet_saved id=%s", getattr(facet, "id", None)))
    widget.facet_deleted.connect(lambda facet: test_logger.debug("facet_deleted id=%s", getattr(facet, "id", None)))

    qt_app.processEvents()

    # Test initial empty state
    assert widget.facet is None
    assert not widget.delete_button.isVisible()

    # Test facet creation
    widget.name_field.setText("Response Quality")
    widget.description_field.setPlainText("Evaluate the quality and helpfulness of model responses")
    qt_app.processEvents()

    assert widget.save_button.isEnabled()

    widget.handle_save()
    qt_app.processEvents()

    # Verify facet was created
    created_facet = Facet.get_by_name(temp_dataset, "Response Quality")
    assert created_facet is not None
    assert widget.facet is not None and widget.facet.id == created_facet.id
    assert "facet_saved" in caplog.text

    # Test facet update
    widget.description_field.setPlainText("Updated description for response quality evaluation")
    qt_app.processEvents()
    widget.handle_save()
    qt_app.processEvents()

    refreshed_facet = Facet.get_by_id(temp_dataset, created_facet.id)
    assert refreshed_facet is not None
    assert refreshed_facet.description == "Updated description for response quality evaluation"

    # Test facet deletion
    widget.handle_delete()
    qt_app.processEvents()

    assert Facet.get_by_id(temp_dataset, created_facet.id) is None
    assert widget.facet is None
    assert not widget.delete_button.isVisible()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_facet_validation_prevents_duplicates(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test facet name validation prevents duplicate names.
    
    Verifies that the widget properly validates unique facet names and shows
    appropriate error messages when duplicates are attempted.
    """
    Facet.create(temp_dataset, "Creativity", "Existing creativity facet")
    session = temp_dataset.session
    assert session is not None
    session.flush()
    session.commit()

    caplog.set_level(logging.DEBUG, logger="WidgetFacet")
    test_logger = logging.getLogger("test_widget_facet.validation")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetFacet(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    widget.name_field.setText("Creativity")
    widget.description_field.setPlainText("Duplicate name should fail validation")
    qt_app.processEvents()

    assert not widget.save_button.isEnabled()
    assert not widget.validation_label.isHidden()
    assert "Name must be unique" in widget.validation_label.text()

    # Test that changing to unique name enables save
    widget.name_field.setText("Innovation")
    qt_app.processEvents()

    assert widget.save_button.isEnabled()
    assert widget.validation_label.isHidden()

    widget.deleteLater()
    qt_app.processEvents()


def test_navigation_opens_facet_tab(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    _ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test navigation from sidebar opens appropriate facet tabs.
    
    Verifies that clicking on facets in the navigation sidebar opens the correct
    facet editing interface with proper state initialization.
    """
    logger = logging.getLogger("test_widget_facet.navigation")
    logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, logger)

    facet = Facet.create(temp_dataset, "Accuracy", "Factual accuracy and correctness")

    # Set up widget test environment
    session = temp_dataset.session
    assert session is not None
    session.flush()
    session.commit()

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    widget.sidebar.filter_panel.show_combo.setCurrentText("Facets")
    qt_app.processEvents()

    widget.sidebar.tree_view.item_selected.emit("facet", facet.id)
    qt_app.processEvents()

    existing_widget_id = widget._find_tab_by("facet", facet.id)  # pylint: disable=protected-access
    assert existing_widget_id is not None
    tab_info = widget.tabs[existing_widget_id]
    assert isinstance(tab_info["widget"], WidgetFacet)
    assert tab_info["widget"].name_field.text() == facet.name

    # Test creating new facet tab
    widget.sidebar.tree_view.new_item_requested.emit("Facet")
    qt_app.processEvents()

    new_tab_ids = [
        (wid, info) for wid, info in widget.tabs.items() if info["type"] == "facet" and info["id"] == 0
    ]
    assert new_tab_ids, "Expected a new unsaved facet tab to be created"
    for _, info in new_tab_ids:
        new_widget = info["widget"]
        assert isinstance(new_widget, WidgetFacet)
        assert new_widget.name_field.text() == ""

    widget.deleteLater()
    qt_app.processEvents()
