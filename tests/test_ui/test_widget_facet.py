"""
Test suite for WidgetFacet GUI component.

Tests facet creation, editing, deletion, validation, and navigation functionality.
"""
# pylint: disable=unused-argument
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.facet import Facet
from py_fade.gui.widget_facet import WidgetFacet
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from tests.helpers.ui_helpers import patch_message_boxes, setup_dataset_session

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def test_widget_facet_crud_flow(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
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
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
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
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
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
    setup_dataset_session(temp_dataset)

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

    new_tab_ids = [(wid, info) for wid, info in widget.tabs.items() if info["type"] == "facet" and info["id"] == 0]
    assert new_tab_ids, "Expected a new unsaved facet tab to be created"
    for _, info in new_tab_ids:
        new_widget = info["widget"]
        assert isinstance(new_widget, WidgetFacet)
        assert new_widget.name_field.text() == ""

    widget.deleteLater()
    qt_app.processEvents()


def test_facet_saved_updates_navigation_and_combobox(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that saving a new facet updates both the navigation tree and facet combobox.

    This test reproduces the bug where:
    1. A new facet is created and saved
    2. The navigation tree should be updated to show the new facet
    3. The active facet combobox should include the new facet
    4. If there were no facets, the new one should be set as active
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger("test_widget_facet.propagation")
    logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, logger)

    setup_dataset_session(temp_dataset)

    # Start with no facets
    assert len(Facet.get_all(temp_dataset)) == 0

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Verify initial state - no facets in combobox
    if widget.facet_combo:
        initial_facet_count = widget.facet_combo.count()
        logger.debug("Initial facet count in combobox: %d", initial_facet_count)
        assert initial_facet_count == 0, "Should start with no facets in combobox"

    # Switch navigation to Facets view
    widget.sidebar.filter_panel.show_combo.setCurrentText("Facets")
    qt_app.processEvents()

    # Verify navigation tree shows "No facets available"
    tree = widget.sidebar.tree_view.tree
    initial_tree_item_count = tree.topLevelItemCount()
    logger.debug("Initial tree item count: %d", initial_tree_item_count)
    if initial_tree_item_count > 0:
        first_item = tree.topLevelItem(0)
        logger.debug("First tree item text: %s", first_item.text(0))
        assert "No facets available" in first_item.text(0) or initial_tree_item_count == 0

    # Create a new facet via the new item request signal (simulating clicking "New" button)
    widget.sidebar.tree_view.new_item_requested.emit("Facet")
    qt_app.processEvents()

    # Find the facet tab that was created
    new_facet_tabs = [(wid, info) for wid, info in widget.tabs.items() if info["type"] == "facet" and info["id"] == 0]
    assert len(new_facet_tabs) > 0, "Should create a new facet tab"

    _widget_id, tab_info = new_facet_tabs[0]
    facet_widget = tab_info["widget"]
    assert isinstance(facet_widget, WidgetFacet)

    # Fill in facet details
    facet_widget.name_field.setText("Response Quality")
    facet_widget.description_field.setPlainText("Evaluate the quality and helpfulness of model responses")
    qt_app.processEvents()

    # Save the facet
    logger.debug("Saving facet...")
    facet_widget.handle_save()
    qt_app.processEvents()

    # Verify facet was created in database
    created_facet = Facet.get_by_name(temp_dataset, "Response Quality")
    assert created_facet is not None, "Facet should be saved in database"
    logger.debug("Created facet with id=%d", created_facet.id)

    # BUG: The navigation tree should now show the new facet
    tree_item_count_after_save = tree.topLevelItemCount()
    logger.debug("Tree item count after save: %d", tree_item_count_after_save)

    # Check if tree was updated
    found_in_tree = False
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        logger.debug("Tree item %d: %s", i, item.text(0))
        if "Response Quality" in item.text(0):
            found_in_tree = True
            break

    assert found_in_tree, "Navigation tree should show the newly created facet"

    # BUG: The facet combobox should now include the new facet
    if widget.facet_combo:
        combobox_count_after_save = widget.facet_combo.count()
        logger.debug("Combobox count after save: %d", combobox_count_after_save)
        assert combobox_count_after_save == 1, "Facet combobox should have the new facet"

        # Find the facet in the combobox
        found_in_combo = False
        for i in range(widget.facet_combo.count()):
            if widget.facet_combo.itemText(i) == "Response Quality":
                found_in_combo = True
                logger.debug("Found facet in combobox at index %d", i)
                break

        assert found_in_combo, "Facet combobox should contain 'Response Quality'"

        # Since this was the first facet, it should be set as active
        assert widget.current_facet_id == created_facet.id, "First facet should be set as active"
        assert widget.current_facet == created_facet, "Current facet should be set"

    widget.deleteLater()
    qt_app.processEvents()


def test_facet_deleted_updates_navigation_and_combobox(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
    ensure_google_icon_font: None,  # Used for side effect of loading icon font
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that deleting a facet updates both the navigation tree and facet combobox.

    Verifies that when a facet is deleted:
    1. The navigation tree is refreshed to remove the deleted facet
    2. The facet combobox is updated to remove the deleted facet
    3. The tab is closed
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger("test_widget_facet.deletion")
    logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, logger)

    # Create initial facets
    facet1 = Facet.create(temp_dataset, "Accuracy", "Factual accuracy")
    _facet2 = Facet.create(temp_dataset, "Creativity", "Creative responses")
    temp_dataset.commit()

    setup_dataset_session(temp_dataset)

    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()

    # Verify initial state - 2 facets in combobox
    if widget.facet_combo:
        assert widget.facet_combo.count() == 2, "Should have 2 facets in combobox"

    # Switch navigation to Facets view
    widget.sidebar.filter_panel.show_combo.setCurrentText("Facets")
    qt_app.processEvents()

    # Verify navigation tree shows both facets
    tree = widget.sidebar.tree_view.tree
    initial_count = tree.topLevelItemCount()
    logger.debug("Initial tree item count: %d", initial_count)
    assert initial_count == 2, "Tree should show 2 facets"

    # Open the first facet for editing
    widget.sidebar.tree_view.item_selected.emit("facet", facet1.id)
    qt_app.processEvents()

    # Find the facet widget
    widget_id = widget._find_tab_by("facet", facet1.id)  # pylint: disable=protected-access
    assert widget_id is not None
    facet_widget = widget.tabs[widget_id]["widget"]
    assert isinstance(facet_widget, WidgetFacet)

    # Delete the facet
    logger.debug("Deleting facet...")
    facet_widget.handle_delete()
    qt_app.processEvents()

    # Verify facet was deleted from database
    deleted_facet = Facet.get_by_id(temp_dataset, facet1.id)
    assert deleted_facet is None, "Facet should be deleted from database"

    # Navigation tree should now show only 1 facet
    tree_count_after_delete = tree.topLevelItemCount()
    logger.debug("Tree item count after delete: %d", tree_count_after_delete)
    assert tree_count_after_delete == 1, "Tree should show only 1 facet after deletion"

    # Verify the remaining facet is the correct one
    remaining_item = tree.topLevelItem(0)
    logger.debug("Remaining tree item: %s", remaining_item.text(0))
    assert "Creativity" in remaining_item.text(0), "Tree should show 'Creativity' facet"

    # Facet combobox should now have only 1 facet
    if widget.facet_combo:
        combobox_count_after_delete = widget.facet_combo.count()
        logger.debug("Combobox count after delete: %d", combobox_count_after_delete)
        assert combobox_count_after_delete == 1, "Facet combobox should have 1 facet remaining"

    widget.deleteLater()
    qt_app.processEvents()
