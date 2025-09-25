from __future__ import annotations

from PyQt6.QtCore import Qt

from py_fade.dataset.facet import Facet
from py_fade.gui.widget_navigation_sidebar import (
    WidgetNavigationFilterPanel,
    WidgetNavigationSidebar,
    WidgetNavigationTree,
)


def test_filter_panel_builds_text_search_filter(qt_app):
    panel = WidgetNavigationFilterPanel()
    panel.search_input.setText("  Important  ")
    qt_app.processEvents()

    criteria = panel.get_filter_criteria()

    assert criteria["show"] == "Samples by Group"
    assert criteria["data_filter"].filters == [{"type": "text_search", "value": "important"}]


def test_navigation_tree_lists_facets(temp_dataset, qt_app):
    Facet.create(temp_dataset, "Evaluation", "Primary facet")
    temp_dataset.commit()

    tree = WidgetNavigationTree()
    criteria = {
        "show": "Facets",
        "data_filter": temp_dataset,  # placeholder, replaced below
    }
    # Replace placeholder with empty DataFilter to avoid importing here.
    from py_fade.dataset.data_filter import DataFilter

    criteria["data_filter"] = DataFilter([])

    tree.update_content(criteria, temp_dataset)
    qt_app.processEvents()

    assert tree.tree.topLevelItemCount() == 1
    facet_item = tree.tree.topLevelItem(0)
    assert facet_item is not None
    assert facet_item.text(0) == "Evaluation"
    assert facet_item.data(0, Qt.ItemDataRole.UserRole) == "facet"


def test_navigation_sidebar_emits_selection(app_with_dataset, temp_dataset, ensure_google_icon_font, qt_app):
    # Ensure a facet exists so the sidebar initialises correctly.
    facet = Facet.create(temp_dataset, "Context", "Sidebar facet")
    temp_dataset.commit()

    selections: list[tuple[str, int]] = []
    sidebar = WidgetNavigationSidebar(None, app_with_dataset)
    sidebar.item_selected.connect(lambda item_type, item_id: selections.append((item_type, item_id)))
    sidebar.filter_panel.show_combo.setCurrentText("Facets")
    qt_app.processEvents()
    qt_app.processEvents()

    tree_item = sidebar.tree_view.tree.topLevelItem(0)
    assert tree_item is not None
    sidebar.tree_view._on_item_clicked(tree_item, 0)
    qt_app.processEvents()

    assert selections
    item_type, item_id = selections[-1]
    assert item_type in {"sample", "facet"}
    if item_type == "facet":
        assert item_id == facet.id
