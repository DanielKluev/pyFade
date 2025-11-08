"""
Test suite for WidgetSampleFilter GUI component.

Tests sample filter creation, editing, deletion, validation, and rule management.
"""
# pylint: disable=unused-argument,protected-access
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from py_fade.dataset.sample_filter import SampleFilter
from py_fade.dataset.tag import Tag
from py_fade.gui.widget_sample_filter import WidgetSampleFilter
from tests.helpers.ui_helpers import patch_message_boxes

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def test_widget_sample_filter_creation(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                       ensure_google_icon_font: None, monkeypatch: pytest.MonkeyPatch,
                                       caplog: pytest.LogCaptureFixture) -> None:
    """
    Test creating a new sample filter through the WidgetSampleFilter interface.
    """
    caplog.set_level(logging.DEBUG, logger="WidgetSampleFilter")
    test_logger = logging.getLogger("test_widget_sample_filter.creation")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, None)
    widget.sample_filter_saved.connect(lambda f: test_logger.debug("sample_filter_saved id=%s", getattr(f, "id", None)))

    qt_app.processEvents()

    assert widget.sample_filter is None
    assert not widget.delete_button.isVisible()
    assert len(widget.current_rules) == 0

    # Fill in basic info
    widget.name_field.setText("Test Filter")
    widget.description_field.setPlainText("A test filter for validation")
    qt_app.processEvents()

    assert widget.save_button.isEnabled()

    # Save the filter
    widget.handle_save()
    qt_app.processEvents()

    # Verify creation
    created_filter = SampleFilter.get_by_name(temp_dataset, "Test Filter")
    assert created_filter is not None
    assert widget.sample_filter is not None
    assert widget.sample_filter.id == created_filter.id
    assert "Creating sample filter" in caplog.text

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_filter_with_rules(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                         ensure_google_icon_font: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test creating a sample filter with rules.
    """
    test_logger = logging.getLogger("test_widget_sample_filter.rules")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a tag for testing
    tag = Tag.create(temp_dataset, "TestTag", "Test tag description")
    temp_dataset.commit()

    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    # Add rules directly (simulating dialog results)
    widget.current_rules = [
        {
            "type": "string",
            "value": "important",
            "negated": False
        },
        {
            "type": "tag",
            "value": tag.id,
            "negated": False
        },
    ]
    widget._refresh_rules_list()
    qt_app.processEvents()

    # Check rules are displayed
    assert widget.rules_list.count() == 2

    # Fill in basic info and save
    widget.name_field.setText("Important Tagged Items")
    widget.description_field.setPlainText("Items that are important and tagged")
    qt_app.processEvents()

    widget.handle_save()
    qt_app.processEvents()

    # Verify the filter was saved with rules
    saved_filter = SampleFilter.get_by_name(temp_dataset, "Important Tagged Items")
    assert saved_filter is not None
    assert len(saved_filter.get_rules()) == 2

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_filter_edit_existing(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                            ensure_google_icon_font: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test editing an existing sample filter.
    """
    test_logger = logging.getLogger("test_widget_sample_filter.edit")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a filter first
    rules = [{"type": "string", "value": "test", "negated": False}]
    existing_filter = SampleFilter.create(temp_dataset, "Original Name", "Original description", filter_rules=rules)
    temp_dataset.commit()

    # Refresh to ensure ID is set
    temp_dataset.get_session().refresh(existing_filter)

    # Load it in the widget
    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, existing_filter)
    qt_app.processEvents()

    assert widget.sample_filter is not None
    assert widget.name_field.text() == "Original Name"
    assert len(widget.current_rules) == 1

    # Modify the filter
    widget.name_field.setText("Updated Name")
    widget.description_field.setPlainText("Updated description")
    qt_app.processEvents()

    widget.handle_save()
    qt_app.processEvents()

    # Verify update
    updated_filter = SampleFilter.get_by_id(temp_dataset, existing_filter.id)
    assert updated_filter is not None
    assert updated_filter.name == "Updated Name"
    assert updated_filter.description == "Updated description"

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_filter_delete(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                     ensure_google_icon_font: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test deleting a sample filter.
    """
    test_logger = logging.getLogger("test_widget_sample_filter.delete")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    # Create a filter
    existing_filter = SampleFilter.create(temp_dataset, "To Delete", "Will be deleted")
    temp_dataset.commit()

    # Refresh to ensure ID is set
    temp_dataset.get_session().refresh(existing_filter)
    filter_id = existing_filter.id

    # Load and delete
    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, existing_filter)
    qt_app.processEvents()

    widget.handle_delete()
    qt_app.processEvents()

    # Verify deletion
    assert SampleFilter.get_by_id(temp_dataset, filter_id) is None
    assert widget.sample_filter is None

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_filter_validation(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                         ensure_google_icon_font: None) -> None:
    """
    Test validation prevents duplicate names and empty fields.
    """
    # Create an existing filter
    SampleFilter.create(temp_dataset, "Existing Filter", "Already exists")
    temp_dataset.commit()

    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    # Try to use existing name
    widget.name_field.setText("Existing Filter")
    widget.description_field.setPlainText("Valid description")
    qt_app.processEvents()

    # Should show validation error
    assert not widget.save_button.isEnabled()
    assert "unique" in widget.validation_label.text().lower()

    # Change to unique name
    widget.name_field.setText("Unique Filter")
    qt_app.processEvents()

    # Should be valid now
    assert widget.save_button.isEnabled()

    widget.deleteLater()
    qt_app.processEvents()


def test_widget_sample_filter_remove_rule(app_with_dataset: "pyFadeApp", temp_dataset: "DatasetDatabase", qt_app: "QApplication",
                                          ensure_google_icon_font: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test removing a rule from the filter.
    """
    test_logger = logging.getLogger("test_widget_sample_filter.remove_rule")
    test_logger.setLevel(logging.DEBUG)
    patch_message_boxes(monkeypatch, test_logger)

    widget = WidgetSampleFilter(None, app_with_dataset, temp_dataset, None)
    qt_app.processEvents()

    # Add multiple rules
    widget.current_rules = [
        {
            "type": "string",
            "value": "first",
            "negated": False
        },
        {
            "type": "string",
            "value": "second",
            "negated": False
        },
        {
            "type": "string",
            "value": "third",
            "negated": False
        },
    ]
    widget._refresh_rules_list()
    qt_app.processEvents()

    assert widget.rules_list.count() == 3

    # Select and remove the second rule
    widget.rules_list.setCurrentRow(1)
    qt_app.processEvents()

    widget._on_remove_rule_clicked()
    qt_app.processEvents()

    # Verify rule was removed
    assert len(widget.current_rules) == 2
    assert widget.rules_list.count() == 2
    assert widget.current_rules[0]["value"] == "first"
    assert widget.current_rules[1]["value"] == "third"

    widget.deleteLater()
    qt_app.processEvents()
