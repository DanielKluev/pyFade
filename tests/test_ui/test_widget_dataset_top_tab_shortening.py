"""
Test tab title shortening in WidgetDatasetTop.

This module tests that tab titles are properly shortened when they exceed 8 words,
and that tooltips display the full title.
"""
# pylint: disable=unused-argument,redefined-outer-name
from __future__ import annotations

import pathlib

import pytest

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.gui.widget_dataset_top import WidgetDatasetTop
from tests.helpers.ui_helpers import setup_test_app_with_fake_home
from tests.helpers.data_helpers import create_test_sample


@pytest.fixture
def dataset_widget(
    temp_dataset: DatasetDatabase,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    qt_app,
    ensure_google_icon_font,
) -> WidgetDatasetTop:
    """
    Create a WidgetDatasetTop instance for testing.
    
    Returns the widget instance with a test dataset loaded.
    """
    app = setup_test_app_with_fake_home(temp_dataset, tmp_path, monkeypatch)
    widget = WidgetDatasetTop(None, app, temp_dataset)
    qt_app.processEvents()
    yield widget
    widget.deleteLater()


def test_short_sample_title_not_shortened(dataset_widget: WidgetDatasetTop, qt_app) -> None:
    """
    Test that short sample titles are not shortened.
    
    Verifies that sample tabs with short titles (8 words or less) display
    the full title without modification.
    """
    # Create a sample with a short title using helper
    sample, _ = create_test_sample(dataset_widget.dataset, title="Simple short title")
    
    # Create tab
    widget_id = dataset_widget.create_sample_tab(sample, focus=True)
    qt_app.processEvents()
    
    # Get tab index
    index = dataset_widget._tab_index(widget_id)
    assert index >= 0
    
    # Verify title is not shortened
    tab_text = dataset_widget.tab_widget.tabText(index)
    expected_title = "S: Simple short title"
    assert tab_text == expected_title
    
    # Verify tooltip shows full title
    tooltip = dataset_widget.tab_widget.tabToolTip(index)
    assert tooltip == expected_title


def test_long_sample_title_shortened(dataset_widget: WidgetDatasetTop, qt_app) -> None:
    """
    Test that long sample titles are properly shortened.
    
    Verifies that sample tabs with long titles (more than 8 words) display
    a shortened version with first 6 and last 2 words.
    """
    # Create a sample with a long title using helper
    long_title = "This is a very long sample title that should be shortened properly"
    sample, _ = create_test_sample(dataset_widget.dataset, title=long_title)
    
    # Create tab
    widget_id = dataset_widget.create_sample_tab(sample, focus=True)
    qt_app.processEvents()
    
    # Get tab index
    index = dataset_widget._tab_index(widget_id)
    assert index >= 0
    
    # Verify title is shortened (S: + 12 words = 13 words total, should be shortened)
    tab_text = dataset_widget.tab_widget.tabText(index)
    expected_shortened = "S: This is a very long ... shortened properly"
    assert tab_text == expected_shortened
    
    # Verify tooltip shows full title
    tooltip = dataset_widget.tab_widget.tabToolTip(index)
    expected_full = f"S: {long_title}"
    assert tooltip == expected_full


def test_tab_title_update_shortened(dataset_widget: WidgetDatasetTop, qt_app) -> None:
    """
    Test that tab title updates are also shortened.
    
    Verifies that when a tab title is updated (e.g., after saving), the new
    title is also shortened if it exceeds 8 words.
    """
    # Create a sample with a short title using helper
    sample, _ = create_test_sample(dataset_widget.dataset, title="Short")
    
    # Create tab
    widget_id = dataset_widget.create_sample_tab(sample, focus=True)
    qt_app.processEvents()
    
    # Simulate the title update that happens after save with a long title
    long_title = "This is a much longer title that should be shortened after update"
    dataset_widget._set_tab_title(widget_id, f"S: {long_title}")
    qt_app.processEvents()
    
    # Get tab index
    index = dataset_widget._tab_index(widget_id)
    assert index >= 0
    
    # Verify title is shortened (13 words total)
    tab_text = dataset_widget.tab_widget.tabText(index)
    expected_shortened = "S: This is a much longer ... after update"
    assert tab_text == expected_shortened
    
    # Verify tooltip shows full title
    tooltip = dataset_widget.tab_widget.tabToolTip(index)
    expected_full = f"S: {long_title}"
    assert tooltip == expected_full


def test_new_sample_tab_short_title(dataset_widget: WidgetDatasetTop, qt_app) -> None:
    """
    Test that 'New Sample' tabs are not shortened.
    
    Verifies that tabs for new samples (without saved data) have short titles
    that don't need shortening.
    """
    # Create a new sample tab (None parameter)
    widget_id = dataset_widget.create_sample_tab(None, focus=True)
    qt_app.processEvents()
    
    # Get tab index
    index = dataset_widget._tab_index(widget_id)
    assert index >= 0
    
    # Verify title
    tab_text = dataset_widget.tab_widget.tabText(index)
    assert tab_text == "New Sample"
    
    # Verify tooltip shows same title
    tooltip = dataset_widget.tab_widget.tabToolTip(index)
    assert tooltip == "New Sample"
