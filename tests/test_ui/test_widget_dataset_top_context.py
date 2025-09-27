"""Tests for the dataset workspace QMainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMainWindow

from py_fade.dataset.facet import Facet
from py_fade.gui.widget_dataset_top import WidgetDatasetTop

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication
    from py_fade.app import pyFadeApp
    from py_fade.dataset.dataset import DatasetDatabase


def _create_dataset_widget(
    app_with_dataset: "pyFadeApp",
    temp_dataset: "DatasetDatabase",
    qt_app: "QApplication",
) -> WidgetDatasetTop:
    widget = WidgetDatasetTop(None, app_with_dataset, temp_dataset)
    qt_app.processEvents()
    return widget


def test_context_selection_persisted_and_reloaded(
    app_with_dataset,
    temp_dataset,
    ensure_google_icon_font,
    qt_app,
):
    """Context changes persist to config and reapply when widget reloads."""
    _ = ensure_google_icon_font
    facet = Facet.create(temp_dataset, "Primary Facet", "Facet used for context tests")
    temp_dataset.commit()

    widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
    try:
        assert widget.facet_combo is not None
        assert widget.model_combo is not None
        facet_index = widget.facet_combo.findText(facet.name)
        assert facet_index >= 0
        widget.facet_combo.setCurrentIndex(facet_index)
        widget._on_facet_selection_changed(  # pylint: disable=protected-access
            facet_index
        )
        qt_app.processEvents()

        key = str(temp_dataset.db_path.resolve())
        prefs = app_with_dataset.config.dataset_preferences.get(key, {})
        assert prefs.get("facet_id") == facet.id
        assert prefs.get("model_name") == widget.current_model_name

        sample_widgets = [
            info["widget"] for info in widget.tabs.values() if info["type"] == "sample"
        ]
        assert sample_widgets
        sample_widget = sample_widgets[0]
        assert sample_widget.active_facet is not None
        assert sample_widget.active_facet.id == facet.id
        assert sample_widget.active_model_name == widget.current_model_name
    finally:
        widget.deleteLater()
        qt_app.processEvents()

    widget_reloaded = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
    try:
        assert widget_reloaded.facet_combo is not None
        assert widget_reloaded.facet_combo.currentData() == facet.id
        assert widget_reloaded.current_model_name == prefs.get("model_name")
    finally:
        widget_reloaded.deleteLater()
        qt_app.processEvents()


def test_close_tab_keeps_overview_and_removes_sample(
    app_with_dataset,
    temp_dataset,
    ensure_google_icon_font,
    qt_app,
):
    """Closing a tab removes it while keeping non-closable overview tab present."""
    _ = ensure_google_icon_font
    Facet.create(temp_dataset, "Aux", "Facet for close tab test")
    temp_dataset.commit()

    widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
    try:
        initial_count = widget.tab_widget.count()
        extra_tab_id = widget.create_sample_tab(None, focus=True)
        qt_app.processEvents()
        assert extra_tab_id in widget.tabs
        extra_widget = widget.tabs[extra_tab_id]["widget"]
        extra_index = widget.tab_widget.indexOf(extra_widget)
        assert extra_index >= 0

        widget.close_tab(extra_index)
        qt_app.processEvents()

        assert widget.tab_widget.count() == initial_count
        assert extra_tab_id not in widget.tabs

        overview_index = widget.tab_widget.indexOf(widget.overview_widget)
        widget.close_tab(overview_index)
        qt_app.processEvents()

        assert id(widget.overview_widget) in widget.tabs
        assert widget.tab_widget.count() > 0
    finally:
        widget.deleteLater()
        qt_app.processEvents()


def test_qmainwindow_menu_bar_is_external(
    app_with_dataset,
    temp_dataset,
    ensure_google_icon_font,
    qt_app,
):
    """Dataset workspace should use QMainWindow with menu bar outside central widget."""

    _ = ensure_google_icon_font
    Facet.create(temp_dataset, "Menu Test Facet", "Facet to ensure menu layout")
    temp_dataset.commit()

    widget = _create_dataset_widget(app_with_dataset, temp_dataset, qt_app)
    try:
        assert isinstance(widget, QMainWindow)
        assert widget.menu_bar is widget.menuBar()
        assert widget.menu_bar is not None
        assert widget.menu_bar.parentWidget() is widget

        central_widget = widget.centralWidget()
        assert central_widget is not None
        layout = central_widget.layout()
        assert layout is not None
        assert layout.count() == 1
        first_item = layout.itemAt(0)
        assert first_item is not None
        assert first_item.widget() is widget.main_splitter
        assert widget.main_splitter.parentWidget() is central_widget
    finally:
        widget.deleteLater()
        qt_app.processEvents()
